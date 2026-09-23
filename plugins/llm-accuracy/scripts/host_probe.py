"""Bounded Claude CLI probes; raw responses stay in memory and are never logged."""

from __future__ import annotations

from contextlib import contextmanager
import io
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
        for word in ("unauthorized", "authentication", "login", "oauth", "credential")
    ):
        return "authentication"
    if any(
        word in lowered for word in ("rate limit", "rate_limit", "hit your session limit")
    ) or re.search(
        r"\b429\b", lowered
    ):
        return "rate_limit"
    return "host_error"


def failure_text(results: list[dict], stderr: str) -> str:
    """Read error-bearing fields only; metadata and successful answers are not causes."""
    parts = [stderr]
    for result in results:
        if isinstance(result.get("result"), str):
            parts.append(result["result"])
        errors = result.get("errors")
        if isinstance(errors, list):
            parts.extend(error for error in errors if isinstance(error, str))
    return "\n".join(parts)


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
    failed = [
        e for e in results if e.get("is_error") or e.get("subtype", "success") != "success"
    ]
    errors = exit_code != 0 or bool(failed)
    hooks = [
        e
        for e in events
        if e.get("type") == "system" and e.get("subtype") == "hook_response"
    ]
    context_count = sum(
        "CLAIM FIDELITY CHECK" in str(e.get("stdout", "")) for e in hooks
    )
    models = [
        e.get("model")
        for e in events
        if e.get("type") == "system" and e.get("subtype") == "init"
    ]
    model = models[0] if models and all(m == models[0] for m in models) else None
    return {
        "status": error_category(failure_text(failed, stderr))
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
        "host_inventory": host_inventory(events),
        "resolved_model": model
        if isinstance(model, str) and re.fullmatch(r"claude-[a-z0-9.-]{1,80}", model)
        else "unreported",
    }


def host_inventory(events: list[dict]) -> dict:
    """Attest reported inventory sizes without exposing host names or paths."""
    initial = [
        e for e in events if e.get("type") == "system" and e.get("subtype") == "init"
    ]
    if not initial:
        return {"status": "unreported"}
    event = initial[0]
    if not all(
        isinstance(e.get(k), list)
        for e in initial
        for k in ("tools", "mcp_servers", "plugins")
    ):
        return {"status": "unreported"}
    if any(
        e[k] != event[k]
        for e in initial[1:]
        for k in ("tools", "mcp_servers", "plugins")
    ):
        return {"status": "changed"}
    return {
        "status": "reported",
        "tool_count": len(event["tools"]),
        "mcp_count": len(event["mcp_servers"]),
        "plugin_count": len(event["plugins"]),
        "accuracy_plugin_count": sum(
            isinstance(p, dict) and p.get("name") == "llm-accuracy"
            for p in event["plugins"]
        ),
        "telemetry_plugin_count": sum(
            isinstance(p, dict) and p.get("name") == "telemetry"
            for p in event["plugins"]
        ),
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


def _feed(stream, prompts, ready, stopped, events) -> None:
    """Write off the deadline thread; one prompt is released per result."""
    try:
        for prompt in prompts:
            ready.acquire()
            if stopped.is_set():
                break
            stream.write(prompt)
            stream.flush()
    except (OSError, ValueError):
        events.put(("stdin_error", None))
    finally:
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _exchange(process, stdin: str, timeout: int) -> tuple[str, str, bool]:
    """Bound both input delivery and output capture, including stalled readers."""
    deadline = time.monotonic() + timeout
    events: queue.Queue = queue.Queue()
    for name in ("stdout", "stderr"):
        threading.Thread(
            target=_drain, args=(getattr(process, name), name, events), daemon=True
        ).start()
    ready, stopped = threading.Semaphore(1), threading.Event()
    feeder = threading.Thread(
        target=_feed,
        args=(process.stdin, io.StringIO(stdin), ready, stopped, events),
        daemon=True,
    )
    process._accuracy_feeder_owned = True
    try:
        feeder.start()
    except RuntimeError:
        process._accuracy_feeder_owned = False
        raise
    input_failed = False
    outputs, closed, size, line = {"stdout": [], "stderr": []}, 0, 0, ""
    try:
        while closed < 2:
            name, chunk = events.get(timeout=max(0, deadline - time.monotonic()))
            if name == "overflow":
                raise OverflowError
            if name == "stdin_error":
                input_failed = True
                continue
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
                    if _is_result(line):
                        ready.release()
                    line = ""
        process.wait(timeout=max(0, deadline - time.monotonic()))
        return "".join(outputs["stdout"]), "".join(outputs["stderr"]), input_failed
    finally:
        # Unblock a feeder waiting for the next result on every exit path.
        # communicate kills the owned child before closing a blocked writer.
        stopped.set()
        ready.release()


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
    if not getattr(process, "_accuracy_feeder_owned", False):
        try:
            process.stdin.close()
        except (OSError, ValueError):
            pass


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
        stdout, stderr, input_failed = _exchange(process, stdin, timeout)
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
    result = parse_events(stdout, stderr, process.returncode)
    if input_failed and result["status"] == "ok":
        return {"status": "host_error", "answers": []}
    return result


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
    prompts: list[str],
    plugin: Path | None,
    *,
    model: str = "sonnet",
    timeout: int = 60,
    effort: str | None = None,
) -> dict:
    """Run an auth-only temporary profile with no tools, MCPs or saved session."""
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,100}", model):
        return {"status": "invalid_model", "answers": []}
    if effort is not None and effort not in {"low", "medium", "high", "xhigh", "max"}:
        return {"status": "invalid_effort", "answers": []}
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
        if effort is not None:
            command.extend(["--effort", effort])
        stdin = (
            "\n".join(
                json.dumps({"type": "user", "message": {"role": "user", "content": p}})
                for p in prompts
            )
            + "\n"
        )
        return communicate(command, root, env, stdin, timeout)
