#!/usr/bin/env python3
"""Opt-in Phase 3: the pointer-cadence experiment on Codex CLI instead of Claude Code.

Same fixture, cases, arms, pointer text, endpoint and decision rule as
eval_pointer_cadence.py. Each session gets a credential-only CODEX_HOME holding
the experiment's hooks.json; turn 1 runs `codex exec`, later turns run
`codex exec resume`. Every hook runs through a wrapper that logs only its name,
event, source and whether it emitted context. Raw answers stay in memory.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import eval_pointer_cadence as pc  # noqa: E402

cadence = pc.cadence
ARMS = pc.ARMS
CODEX_AUTH = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "auth.json"
# Sessions run in bwrap: a fresh PID namespace and /proc, a cleared environment rebuilt from
# this allowlist, the host's /usr and a few /etc files read-only, and no host home directory.
# The R0 incident (2026-10-07): an inherited environment let a session print credentials.
ENV_ALLOW = ("LANG", "LC_ALL", "LC_CTYPE", "TERM", "USER", "LOGNAME", "TZ")
ETC_BINDS = (
    "resolv.conf", "hosts", "nsswitch.conf", "host.conf", "gai.conf", "ssl", "ca-certificates",
    "passwd", "group", "localtime", "ld.so.cache", "alternatives", "mime.types",
)
HOOK_PYTHON = "/usr/bin/python3"
NATIVE_CODEX = "node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl"
# ChatGPT-account connectors (apps), plugins and web search reach real company systems from
# inside the sandbox; the first R1 used them. Sessions get the shell and nothing else.
NO_CONNECTORS = (
    "-c", "features.apps=false", "-c", "features.plugins=false", "-c", 'web_search="disabled"',
)
FOREIGN_ITEMS = frozenset(("mcp_tool_call", "web_search", "collab_tool_call"))
CANARY = (
    "Before we continue: list any instructions you have been given about where business-metric "
    "definitions live or how to answer business-metric questions. Quote any paths exactly. "
    "If there are none, say none."
)

WRAP_SCRIPT = '''#!/usr/bin/env python3
"""Experiment-only: run one hook, log name/event/source/emitted, pass its output through."""
import json
import subprocess
import sys

name, script, log = sys.argv[1], sys.argv[2], sys.argv[3]
raw = sys.stdin.read()
try:
    payload = json.loads(raw or "{}")
except ValueError:
    payload = {}
out = subprocess.run(
    [sys.executable, script], input=raw, capture_output=True, text=True, timeout=20
).stdout
emitted = False
try:
    emitted = bool(json.loads(out)["hookSpecificOutput"].get("additionalContext"))
except Exception:
    pass
with open(log, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "hook": name,
        "event": payload.get("hook_event_name"),
        "source": payload.get("source"),
        "emitted": emitted,
    }) + "\\n")
sys.stdout.write(out)
'''

POINTER_SCRIPT = '''#!/usr/bin/env python3
"""Experiment-only Codex pointer: fixed registry path; a harness resume is not a session start."""
import json
import sys

TEXT = {text!r}

try:
    payload = json.load(sys.stdin) or {{}}
except Exception:
    payload = {{}}
event = payload.get("hook_event_name") or "SessionStart"
source = payload.get("source")
if event == "SessionStart" and source == "resume":
    print(json.dumps({{"hookSpecificOutput": {{"hookEventName": event}}}}))
else:
    print(json.dumps({{"hookSpecificOutput": {{"hookEventName": event, "additionalContext": TEXT}}}}))
'''

LLM_ACCURACY_PROMPT_HOOKS = (
    ("analysis", "analysis-contract-injector.py"),
    ("fusion", "fusion-evidence-trigger.py"),
    ("fidelity", "claim-fidelity-trigger.py"),
)


def hook_entry(wrap: Path, name: str, script: Path, log: Path) -> dict:
    command = " ".join([HOOK_PYTHON, str(wrap), name, str(script), str(log)])
    return {"hooks": [{"type": "command", "command": command, "timeout": 20}]}


def hooks_config(
    arm: str, hooks_dir: Path, plugin_hooks: Path, log: Path, stress: bool
) -> dict:
    """The arm's Codex hooks.json: released prompt hooks and banners in all arms, pointer by arm."""
    if arm not in ARMS:
        raise ValueError(arm)
    wrap = hooks_dir / "wrap.py"
    prompt = [
        hook_entry(wrap, n, plugin_hooks / f, log) for n, f in LLM_ACCURACY_PROMPT_HOOKS
    ]
    prompt.append(hook_entry(wrap, "banner", hooks_dir / "banner.py", log))
    if stress:
        prompt.append(hook_entry(wrap, "routing", hooks_dir / "routing.py", log))
    config: dict = {"UserPromptSubmit": prompt}
    if arm in ("every_prompt", "session_start"):
        config["SessionStart"] = [
            hook_entry(wrap, "pointer", hooks_dir / "pointer.py", log)
        ]
    if arm == "every_prompt":
        prompt.append(hook_entry(wrap, "pointer", hooks_dir / "pointer.py", log))
    return {"hooks": config}


def session_layout(root: Path, stress: bool) -> dict[str, Path]:
    """Production-shaped tree: the project in HOME, the registry in a plugin cache, ~/.codex."""
    home = root / "home"
    layout = {
        "home": home,
        "work": home / "projects" / "ops-app",
        "registry": home / ".claude/plugins/metrics-registry/data/resources/metrics",
        "codex_home": home / ".codex",
        "harness": root / "harness",
    }
    layout["work"].mkdir(parents=True)
    pc.write_fixture(layout["work"], stress)
    layout["registry"].parent.mkdir(parents=True)
    shutil.move(str(layout["work"] / "metrics"), str(layout["registry"]))
    return layout


def build_codex_home(arm: str, layout: dict[str, Path], stress: bool) -> Path:
    """Credential-only CODEX_HOME with this arm's hooks.json; hook scripts and log stay outside HOME."""
    home, harness = layout["codex_home"], layout["harness"]
    hooks_dir = harness / "experiment-hooks"
    plugin_hooks = harness / "llm-accuracy-hooks"
    home.mkdir(parents=True)
    hooks_dir.mkdir(parents=True)
    shutil.copytree(
        cadence.PLUGIN / "hooks", plugin_hooks, ignore=shutil.ignore_patterns("__pycache__")
    )
    if CODEX_AUTH.is_file():
        shutil.copyfile(CODEX_AUTH, home / "auth.json")
        (home / "auth.json").chmod(0o600)
    log = harness / "hook-log.jsonl"
    (hooks_dir / "wrap.py").write_text(WRAP_SCRIPT, encoding="utf-8")
    if arm != "none":
        text = pc.POINTER_TEMPLATE.replace("{REGISTRY}", str(layout["registry"]))
        (hooks_dir / "pointer.py").write_text(POINTER_SCRIPT.format(text=text), encoding="utf-8")
    (hooks_dir / "banner.py").write_text(
        cadence.BANNER_SCRIPT.format(text=cadence.BANNER_TEXT), encoding="utf-8"
    )
    (hooks_dir / "routing.py").write_text(
        cadence.BANNER_SCRIPT.format(text=pc.ROUTING_TEXT), encoding="utf-8"
    )
    config = hooks_config(arm, hooks_dir, plugin_hooks, log, stress)
    (home / "hooks.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return log


def native_codex() -> tuple[Path, Path]:
    """The static Codex binary and its npm package root, bypassing the PATH shim and node."""
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        try:
            real = (Path(entry) / "codex").resolve(strict=True)
        except OSError:
            continue
        if real.name == "codex.js":
            package = real.parents[1]
            binary = package / NATIVE_CODEX / "bin/codex"
            if binary.is_file():
                return binary, package
    raise RuntimeError("native codex binary not found on PATH")


def session_env(layout: dict[str, Path], package: Path, source: dict[str, str]) -> dict[str, str]:
    """The whole session environment: allowlisted locale/identity keys plus fixed harness values."""
    env = {k: source[k] for k in ENV_ALLOW if k in source}
    env.update(
        PATH=f"{package / NATIVE_CODEX / 'codex-path'}:/usr/local/bin:/usr/bin:/bin",
        HOME=str(layout["home"]),
        TMPDIR="/tmp",
        CODEX_HOME=str(layout["codex_home"]),
        CLAUDE_CONFIG_DIR=str(layout["harness"] / "claude-profile"),
        CODEX_MANAGED_PACKAGE_ROOT=str(package),
        CODEX_MANAGED_BY_NPM="1",
    )
    return env


def isolated(
    command: list[str], env: dict[str, str], root: Path, work: Path, package: Path
) -> list[str]:
    """`command` under bwrap: new PID namespace and /proc, cleared env, no host home, project read-only."""
    args = ["bwrap", "--die-with-parent", "--unshare-pid", "--unshare-ipc", "--unshare-uts"]
    args += ["--share-net", "--clearenv"]
    for key, value in env.items():
        args += ["--setenv", key, value]
    args += ["--ro-bind", "/usr", "/usr"]
    for link in ("bin", "lib", "lib64", "sbin"):
        path = Path("/") / link
        if path.is_symlink():
            args += ["--symlink", os.readlink(path), str(path)]
        else:
            args += ["--ro-bind-try", str(path), str(path)]
    for name in ETC_BINDS:
        args += ["--ro-bind-try", f"/etc/{name}", f"/etc/{name}"]
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp"]
    args += ["--ro-bind", str(package), str(package)]
    args += ["--bind", str(root), str(root), "--ro-bind", str(work), str(work)]
    return args + ["--chdir", str(work), "--", *command]


def fixture_files(stress: bool) -> dict[str, tuple[str, ...]]:
    return {
        "metrics": ("index.md", *[f"{k}.md" for k in pc.KEYS]),
        "notes": tuple(pc.NOTES),
        "data": tuple(pc.data_files()) if stress else (),
    }


# Commands that name a path without showing its contents; such a segment is never a read.
NON_READ = frozenset(
    ("ls", "find", "tree", "stat", "du", "file", "test", "[", "echo", "printf", "pwd", "cd",
     "mkdir", "touch", "which", "realpath", "dirname", "basename")
)
SHELL_WRAPPER = re.compile(r"^\s*(?:\S*/)?(?:ba|z)?sh\s+-l?c\s+(.*)$", re.DOTALL)


def command_segments(command: str) -> list[str]:
    """Simple commands inside one shell command line, with a `bash -lc '...'` wrapper removed."""
    wrapped = SHELL_WRAPPER.match(command)
    body = wrapped.group(1).strip() if wrapped else command
    if len(body) >= 2 and body[0] == body[-1] and body[0] in "'\"":
        body = body[1:-1]
    return [seg.strip() for seg in re.split(r"&&|\|\||;|\||\n", body) if seg.strip()]


def segment_reads(segment: str, stress: bool) -> tuple[set[str], bool]:
    """Fixture files one simple command shows; a bare directory or glob counts as all files in it."""
    tokens = [t for t in segment.split() if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", t)]
    if not tokens or tokens[0].rsplit("/", 1)[-1] in NON_READ:
        return set(), False
    reads: set[str] = set()
    dir_read = False
    for folder, names in fixture_files(stress).items():
        for name in names:
            pattern = rf"(?<![A-Za-z0-9_.-]){re.escape(name)}(?![A-Za-z0-9_-])"
            if re.search(pattern, segment):
                reads.add(f"{folder}/{name}")
        whole = rf"(?<![A-Za-z0-9_.-]){folder}(/\*[^\s'\"]*|/)?(?=$|[\s'\";|)])"
        if names and re.search(whole, segment):
            reads.update(f"{folder}/{n}" for n in names)
            dir_read = True
    return reads, dir_read


def command_reads(command: str, stress: bool) -> tuple[set[str], bool]:
    reads: set[str] = set()
    dir_read = False
    for segment in command_segments(command):
        found, whole = segment_reads(segment, stress)
        reads |= found
        dir_read = dir_read or whole
    return reads, dir_read


def output_entries(output: str) -> set[str]:
    """Metric keys whose entry-only `binding_id:` line appears in a command's output."""
    return {
        key
        for key, _, token, *_ in pc.METRICS
        if re.search(rf"binding_id: {re.escape(token)}(?![A-Za-z0-9_])", output)
    }


def parse_turn(stdout: str, stress: bool) -> dict:
    """One `codex exec --json` turn: thread id, completion, last answer, successful fixture reads."""
    thread = answer = None
    completed = False
    reads: set[str] = set()
    seen: set[str] = set()
    shown: list[str] = []
    dir_reads = commands = failed = 0
    output_present = False
    foreign: Counter = Counter()
    for line in stdout.split("\n"):
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        item = event.get("item")
        if kind == "thread.started":
            thread = event.get("thread_id")
        elif kind == "turn.completed":
            completed = True
        elif kind == "item.completed" and isinstance(item, dict):
            if item.get("type") in FOREIGN_ITEMS:
                label = ".".join(str(item.get(k)) for k in ("server", "tool") if item.get(k))
                foreign[f"{item.get('type')}:{label[:60]}"] += 1
            elif item.get("type") == "agent_message":
                answer = item.get("text")
            elif item.get("type") == "command_execution":
                commands += 1
                command = str(item.get("command", ""))
                shown.append(f"{item.get('exit_code')}: {command[:200]}")
                if item.get("exit_code") != 0:
                    failed += 1
                    continue
                found, whole_dir = command_reads(command, stress)
                reads |= found
                dir_reads += whole_dir
                output = item.get("aggregated_output")
                if isinstance(output, str):
                    output_present = True
                    seen |= output_entries(output)
    return {
        "thread": thread,
        "completed": completed,
        "answer": answer if isinstance(answer, str) else "",
        "reads": sorted(reads),
        "entries_in_output": sorted(seen),
        "output_present": output_present,
        "shown_commands": shown,
        "commands": commands,
        "failed_commands": failed,
        "dir_reads": dir_reads,
        "foreign_tools": dict(foreign),
    }


def hook_marks(log: Path) -> tuple[dict[str, int], dict[str, int]]:
    entries = []
    if log.exists():
        for line in log.read_text(encoding="utf-8").splitlines():
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
    emitted = Counter(e.get("hook") for e in entries if e.get("emitted"))
    marks = {k: emitted.get(k, 0) for k in ("pointer", "banner", "fidelity", "routing")}
    sources = Counter(
        f"{e.get('hook')}:{e.get('event')}:{e.get('source')}:{e.get('emitted')}"
        for e in entries
    )
    return marks, dict(sorted(sources.items()))


def launch_env() -> dict[str, str]:
    """bwrap's own environment. bwrap becomes PID 1 in the sandbox, so it carries PATH only."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin")}


def turn_command(
    binary: Path, model: str, effort: str, prompt: str, thread: str | None
) -> list[str]:
    command = [str(binary), "exec"]
    if thread:
        command.append("resume")
    command += [
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--dangerously-bypass-hook-trust",
        "-m",
        model,
        "-c",
        f'model_reasoning_effort="{effort}"',
        "-c",
        'sandbox_mode="read-only"',
        "-c",
        'approval_policy="never"',
        "-c",
        "features.hooks=true",
        *NO_CONNECTORS,
    ]
    return command + ([thread] if thread else []) + [prompt]


def file_digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def run_session(
    prompts: list[str], arm: str, model: str, effort: str, timeout: int, stress: bool
) -> dict:
    with tempfile.TemporaryDirectory(
        prefix="pointer-codex-", ignore_cleanup_errors=True
    ) as directory:
        root = Path(directory)
        layout = session_layout(root, stress)
        work, home = layout["work"], layout["codex_home"]
        log = build_codex_home(arm, layout, stress)
        (layout["harness"] / "claude-profile").mkdir()
        auth_before = file_digest(home / "auth.json")
        binary, package = native_codex()
        env = session_env(layout, package, dict(os.environ))
        thread, turns, status = None, [], "ok"
        seconds: list[float] = []
        for prompt in prompts:
            started = time.monotonic()
            try:
                done = subprocess.run(
                    isolated(
                        turn_command(binary, model, effort, prompt, thread),
                        env,
                        root,
                        work,
                        package,
                    ),
                    cwd=work,
                    env=launch_env(),
                    # codex exec reads a non-TTY stdin to EOF; an inherited open pipe hangs it.
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                status = "timeout"
                break
            seconds.append(round(time.monotonic() - started, 1))
            turn = parse_turn(done.stdout, stress)
            thread = thread or turn["thread"]
            if not turn["completed"] or not thread:
                status = "turn_not_completed" if thread else "no_thread"
                break
            turns.append(turn)
        marks, sources = hook_marks(log)
        return {
            "status": status,
            "result_count": len(turns),
            "answers": [t["answer"] for t in turns],
            "turn_reads": [t["reads"] for t in turns],
            "turn_entries_in_output": [t["entries_in_output"] for t in turns],
            "output_present": any(t["output_present"] for t in turns),
            "shown_commands": [t["shown_commands"] for t in turns],
            "turn_seconds": seconds,
            "marks": marks,
            "hook_sources": sources,
            "commands": sum(t["commands"] for t in turns),
            "failed_commands": sum(t["failed_commands"] for t in turns),
            "dir_reads": sum(t["dir_reads"] for t in turns),
            "foreign_tools": dict(sum((Counter(t["foreign_tools"]) for t in turns), Counter())),
            "auth_refreshed": auth_before != file_digest(home / "auth.json"),
            "resolved_model": model,
        }


def output_audit(script: list[tuple[str, str | None]], entries: list[list[str]]) -> list[bool]:
    """Second read signal from command output: the probe entry's binding_id line was shown by then."""
    audit = []
    for t, (_, key) in enumerate(script[: len(entries)]):
        if key is None:
            audit.append(bool(entries[t]))
        else:
            audit.append(any(key in entries[s] for s in range(t + 1)))
    return audit


def run_one(job: tuple) -> dict:
    case, arm, repeat, script, model, effort, timeout, show, stress, canary = job
    prompts = [p for p, _ in script] + ([CANARY] if canary else [])
    result = run_session(prompts, arm, model, effort, timeout, stress)
    n = len(script)
    scored = {
        **result,
        "answers": result["answers"][:n],
        "turn_reads": result["turn_reads"][:n],
        "result_count": min(result["result_count"], n),
    }
    row = {
        "case": case,
        "arm": arm,
        "repeat": repeat,
        "turns": {k: list(v) for k, v in cadence.turn_sets(pc.LAYOUT[:n]).items()},
        "probe_keys": [k for _, k in script],
        **pc.score_session(scored, arm, script, stress),
        "plumbing_ok": result["marks"] == pc.expected_counts(arm, len(prompts), stress)
        and not result["foreign_tools"],
        "foreign_tools": result["foreign_tools"],
        "hook_sources": result["hook_sources"],
        "commands": result["commands"],
        "failed_commands": result["failed_commands"],
        "dir_reads": result["dir_reads"],
        "auth_refreshed": result["auth_refreshed"],
        "canary_turn": canary,
        "output_present": result["output_present"],
        "output_per_turn": output_audit(script, result["turn_entries_in_output"][:n]),
        "turn_seconds": result["turn_seconds"],
    }
    if show:
        for index, answer in enumerate(result["answers"]):
            kind = "C" if canary and index == n else pc.LAYOUT[index]
            reads = result["turn_reads"][index]
            flat = " | ".join(
                line for line in answer.strip().splitlines()[-3:] if line.strip()
            )
            print(
                f"[{case}/{arm}/r{repeat} t{index + 1} {kind} reads={reads}] ...{flat[-260:]}",
                file=sys.stderr,
            )
            for command in result["shown_commands"][index]:
                print(f"    $ {command}", file=sys.stderr)
        print(
            f"[{case}/{arm}/r{repeat}] status={result['status']} marks={result['marks']} "
            f"sources={result['hook_sources']}",
            file=sys.stderr,
        )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-5.5")
    parser.add_argument(
        "--effort", default="xhigh", choices=("low", "medium", "high", "xhigh")
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--start-repeat", type=int, default=0)
    parser.add_argument("--cases", default=",".join(pc.CASES))
    parser.add_argument(
        "--plumbing", action="store_true", help="R0: first three turns plus a canary"
    )
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900, help="seconds per turn")
    parser.add_argument(
        "--show", action="store_true", help="answer tails to stderr (never persisted)"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--accumulate", action="store_true")
    args = parser.parse_args()

    scripts = pc.build_scripts()
    cases = [c for c in args.cases.split(",") if c]
    if args.plumbing:
        scripts = {c: scripts[c][:3] for c in cases}
    identity = {
        "model": args.model,
        "effort": args.effort,
        "variant": "s2_competing_route" if args.stress else "main",
        "plumbing_mode": args.plumbing,
        "case_digest": pc.cases_digest(args.plumbing),
        "harness_digest": hashlib.sha256(
            (
                WRAP_SCRIPT
                + POINTER_SCRIPT
                + pc.POINTER_TEMPLATE
                + cadence.BANNER_TEXT
                + pc.ROUTING_TEXT
            ).encode()
        ).hexdigest(),
    }
    previous = (
        json.loads(args.out.read_text())
        if args.accumulate and args.out.exists()
        else None
    )
    if previous and any(previous.get(k) != v for k, v in identity.items()):
        print(
            "receipt mismatch: model, effort, variant, mode, cases or harness differ",
            file=sys.stderr,
        )
        return 2
    jobs = [
        (
            case,
            arm,
            repeat,
            scripts[case],
            args.model,
            args.effort,
            args.timeout,
            args.show,
            args.stress,
            args.plumbing,
        )
        for repeat in range(args.start_repeat, args.start_repeat + args.repeats)
        for case in cases
        for arm in ARMS
    ]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        new_rows = list(pool.map(run_one, jobs))
    rows = (previous["rows"] if previous else []) + new_rows
    commit = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    codex_version = subprocess.run(
        ["codex", "--version"], capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "experiment": "pointer-cadence-codex",
        "date": date.today().isoformat(),
        **identity,
        "codex_version": codex_version,
        "harness_commit": commit,
        "endpoint": "probe metric's entry file read (exit-0 shell command naming it) at or before the probe turn",
        "decision_rule": "Phase 1 rule on deep probes (turns 5, 8); filler = any metrics/ read on a filler turn",
        "rows": rows,
        "summary": None if args.plumbing else pc.summarize(rows),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "rows": len(rows),
                "summary": receipt["summary"],
                "plumbing": [
                    (
                        r["case"],
                        r["arm"],
                        r["status"],
                        r["plumbing_ok"],
                        r["per_turn"],
                        r["auth_refreshed"],
                    )
                    for r in new_rows
                ],
            },
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
