"""Bounded Claude CLI probes; raw responses stay in memory and are never logged."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from pathlib import Path


CONTROL_VARS = (
    "CLAUDECODE",
    "LLM_ACCURACY_CONFIG",
    "CC_CLAIM_FIDELITY_MODE",
    "CC_SKIP_ANALYSIS",
    "CC_SKIP_FUSION_EVIDENCE",
    "CC_SKIP_CLAIM_FIDELITY",
    "CC_SKIP_PARTIAL_RESULT",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_MODEL",
)


def error_category(text: str) -> str:
    lowered = text.lower()
    if any(
        word in lowered
        for word in ("expired", "unauthorized", "authentication", "login")
    ):
        return "authentication"
    if any(word in lowered for word in ("rate limit", "rate_limit", "429")):
        return "rate_limit"
    return "host_error"


def parse_events(stdout: str, stderr: str, exit_code: int) -> dict:
    """Keep answers in memory; metadata contains only fixed labels/counts."""
    events = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if isinstance(event, dict):
            events.append(event)
    results = [e for e in events if e.get("type") == "result"]
    errors = exit_code != 0 or any(
        e.get("is_error") or e.get("subtype", "success") != "success" for e in results
    )
    hooks = [
        e
        for e in events
        if e.get("type") == "system" and e.get("subtype") == "hook_response"
    ]
    context_count = sum(
        "CLAIM FIDELITY CHECK" in str(e.get("stdout", "")) for e in hooks
    )
    model = next(
        (
            e.get("model")
            for e in events
            if e.get("type") == "system" and e.get("subtype") == "init"
        ),
        None,
    )
    return {
        "status": error_category(stdout + stderr)
        if errors
        else "ok"
        if results
        else "missing_result",
        "answers": [
            e.get("result", "") for e in results if isinstance(e.get("result"), str)
        ],
        "result_count": len(results),
        "fidelity_hook_responses": context_count,
        "hook_response_count": len(hooks),
        "builtin_signal_responses": sum(
            "PARTIAL RESULT SIGNAL" in str(e.get("stdout", "")) for e in hooks
        ),
        "resolved_model": model
        if isinstance(model, str) and re.fullmatch(r"claude-[a-z0-9.-]{1,80}", model)
        else "unreported",
    }


def _drain(stream, label: str, events: queue.Queue) -> None:
    size = 0
    try:
        while chunk := stream.readline(8192):
            size += len(chunk)
            if size > 4_000_000:
                events.put(("overflow", None))
                break
            events.put((label, chunk))
    finally:
        events.put((label, None))
        stream.close()


def _exchange(process, stdin: str, timeout: int) -> tuple[str, str]:
    """Send each turn only after the previous result; cap captured output."""
    events: queue.Queue = queue.Queue()
    for name in ("stdout", "stderr"):
        threading.Thread(
            target=_drain, args=(getattr(process, name), name, events), daemon=True
        ).start()
    prompts = iter(stdin.splitlines(keepends=True))
    pending = next(prompts, "")
    process.stdin.write(pending)
    process.stdin.flush()
    pending = next(prompts, None)
    if pending is None:
        process.stdin.close()
    outputs, closed, size, line = {"stdout": [], "stderr": []}, 0, 0, ""
    deadline = time.monotonic() + timeout
    while closed < 2:
        name, chunk = events.get(timeout=max(0, deadline - time.monotonic()))
        if name == "overflow":
            raise OverflowError
        if chunk is None:
            closed += 1
            continue
        size += len(chunk)
        if size > 4_000_000:
            raise OverflowError
        outputs[name].append(chunk)
        if name == "stdout":
            line += chunk
            if line.endswith("\n"):
                if pending is not None and _is_result(line):
                    process.stdin.write(pending)
                    process.stdin.flush()
                    pending = next(prompts, None)
                    if pending is None:
                        process.stdin.close()
                line = ""
    process.wait(timeout=max(0, deadline - time.monotonic()))
    return "".join(outputs["stdout"]), "".join(outputs["stderr"])


def _is_result(line: str) -> bool:
    try:
        event = json.loads(line)
        return isinstance(event, dict) and event.get("type") == "result"
    except (ValueError, RecursionError):
        return False


def _kill(process) -> None:
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            # Terminate only this probe's Windows process tree, including the
            # Node child used by some Claude launchers.
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=5,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass
            process.kill()
    except ProcessLookupError:
        pass
    process.wait()
    if not process.stdin.closed:
        process.stdin.close()


def communicate(
    command: list[str], cwd: Path, env: dict, stdin: str, timeout: int
) -> dict:
    """Bound output/time, kill only owned processes, and retain answers in memory."""
    try:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            start_new_session=os.name == "posix",
        )
    except OSError:
        return {"status": "host_unavailable", "answers": []}
    try:
        stdout, stderr = _exchange(process, stdin, timeout)
    except (subprocess.TimeoutExpired, queue.Empty, OverflowError, OSError) as exc:
        _kill(process)
        status = (
            "oversized_output"
            if isinstance(exc, OverflowError)
            else "host_error"
            if isinstance(exc, OSError)
            else "timeout"
        )
        return {"status": status, "answers": []}
    except BaseException:
        # Cancellation and unexpected failures must not leave a detached model
        # process running. Preserve the exception after stopping the owned tree.
        _kill(process)
        raise
    return parse_events(stdout, stderr, process.returncode)


def _terminate(signum, frame) -> None:
    raise SystemExit(128 + signum)


@contextmanager
def _termination_cleanup():
    """Let POSIX CLI termination unwind owned-process and temporary-file cleanup."""
    if os.name != "posix" or threading.current_thread() is not threading.main_thread():
        yield
        return
    previous = signal.signal(signal.SIGTERM, _terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def run_probe(
    prompts: list[str], plugin: Path | None, *, model: str = "sonnet", timeout: int = 60
) -> dict:
    """Run an auth-only temporary profile with no tools, MCPs or saved session."""
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,100}", model):
        return {"status": "invalid_model", "answers": []}
    executable = shutil.which("claude")
    if not executable:
        return {"status": "host_unavailable", "answers": []}
    auth_root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    with (
        _termination_cleanup(),
        tempfile.TemporaryDirectory(prefix="accuracy-probe-") as directory,
    ):
        root = Path(directory)
        profile = root / "profile"
        profile.mkdir()
        auth = auth_root / ".credentials.json"
        try:
            if auth.is_file():
                shutil.copyfile(auth, profile / auth.name)
                (profile / auth.name).chmod(0o600)
        except OSError:
            return {"status": "auth_copy_failed", "answers": []}
        env = {k: v for k, v in os.environ.items() if k not in CONTROL_VARS}
        env["CLAUDE_CONFIG_DIR"] = str(profile)
        command = [
            executable,
            "--print",
            "--input-format",
            "stream-json",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-hook-events",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--mcp-config",
            '{"mcpServers":{}}',
            "--tools",
            "",
            "--no-session-persistence",
            "--model",
            model,
            "--max-budget-usd",
            "1.00",
        ]
        if plugin is not None:
            command.extend(["--plugin-dir", str(plugin.resolve())])
        stdin = (
            "\n".join(
                json.dumps({"type": "user", "message": {"role": "user", "content": p}})
                for p in prompts
            )
            + "\n"
        )
        return communicate(command, root, env, stdin, timeout)
