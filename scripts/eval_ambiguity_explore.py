#!/usr/bin/env python3
"""Opt-in live smoke of the ambiguity reminder on a vague new-customer count.

Each session gets a fresh credential-only profile, no MCP servers, the tools
Bash, Read, Grep and Glob, and a working folder holding a synthetic
``signups.csv`` and README. Every definitional choice in the fixture moves the
July count; ``--print-variants`` shows the oracle. Replies are written only to
``--raw-dir`` (outside the repository) for manual reading; stdout carries
fixed labels, counts and the oracle, never answer text.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/llm-accuracy"
sys.path.insert(0, str(PLUGIN / "scripts"))
import host_probe as probe  # noqa: E402

HOOK = "hooks/analysis-contract-injector.py"
UTC = timezone.utc
LOCAL = timezone(
    timedelta(hours=10)
)  # Australia/Sydney has no daylight saving in July.
FIELDS = (
    "event_id",
    "account_id",
    "email",
    "event",
    "occurred_at",
    "plan",
    "is_test",
    "merged_into",
)
README = (
    "# Billing export\n\n"
    "`signups.csv` holds one row per account event from the billing system, "
    "January to August 2026.\n\n"
    "Columns: event_id, account_id, email, event (signup, trial_started, "
    "subscription_started, subscription_cancelled), occurred_at (ISO 8601, UTC), "
    "plan, is_test, merged_into.\n\n"
    "The company reports in Australia/Sydney time.\n"
)
PROMPTS = {
    "vague": "How many new customers did we get in July?",
    "precise": (
        "How many new customers did we get in July 2026? Count distinct accounts whose first "
        "subscription_started event falls in July in Australia/Sydney time; exclude test "
        "accounts, merged accounts and exact duplicate rows; ignore rows with no timestamp. "
        "Use signups.csv."
    ),
}
AMBIGUITY_MARK = "more than one reasonable interpretation"
ANALYSIS_MARK = "open-ended data analysis"


def make_rows() -> list[dict]:
    """Deterministic synthetic events; each trap is a fixed, countable group."""
    rows, accounts = [], iter(range(1000, 2000))

    def add(account, event, when, *, plan="growth", test=False, merged="", email=None):
        rows.append(
            {
                "event_id": f"e{len(rows) + 1:04d}",
                "account_id": f"a{account}",
                "email": email or f"user{account}@example.com",
                "event": event,
                "occurred_at": when.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                if when
                else "",
                "plan": plan,
                "is_test": "true" if test else "false",
                "merged_into": merged,
            }
        )

    def at(month, day, hour=3):
        return datetime(2026, month, day, hour, tzinfo=LOCAL)

    july_new = []
    for index in range(40):  # genuine new paying customers, mid-July
        account = next(accounts)
        july_new.append(account)
        add(account, "signup", at(6 + index % 2, 5 + index % 20))
        if index % 3 == 0:
            add(
                account,
                "trial_started",
                at(6 + index % 2, 6 + index % 20),
                plan="trial",
            )
        add(account, "subscription_started", at(7, 3 + index % 25))
    for month, total in (
        (3, 12),
        (5, 10),
        (6, 15),
        (8, 15),
    ):  # other months' new customers
        for index in range(total):
            account = next(accounts)
            add(account, "signup", at(month, 2 + index))
            add(account, "subscription_started", at(month, 4 + index))
    for index in range(5):  # test accounts paying in July
        account = next(accounts)
        add(account, "signup", at(7, 2 + index), test=True)
        add(account, "subscription_started", at(7, 3 + index), test=True)
    for hour in (1, 4, 7):  # 1 July in Sydney, still 30 June in UTC
        account = next(accounts)
        add(account, "signup", at(6, 20))
        add(account, "subscription_started", at(7, 1, hour))
    account = next(accounts)  # 1 August in Sydney, still 31 July in UTC
    add(account, "signup", at(7, 20))
    add(account, "subscription_started", at(8, 1, 6))
    for index in range(11):  # July trials that never paid
        account = next(accounts)
        add(account, "signup", at(7, 4 + index))
        add(account, "trial_started", at(7, 4 + index), plan="trial")
    for index in range(3):  # duplicate accounts merged into a July customer
        account, survivor = next(accounts), july_new[index]
        add(
            account,
            "signup",
            at(7, 8 + index),
            merged=f"a{survivor}",
            email=f"user{survivor}@example.com",
        )
        add(
            account,
            "subscription_started",
            at(7, 9 + index),
            merged=f"a{survivor}",
            email=f"user{survivor}@example.com",
        )
    for row in [
        dict(r)
        for r in rows
        if r["event"] == "subscription_started"
        and r["account_id"] in {f"a{a}" for a in july_new[10:15]}
    ]:
        rows.append(row)  # exact duplicate export rows
    for index in range(2):  # July sign-ups whose payment row lost its timestamp
        account = next(accounts)
        add(account, "signup", at(7, 15 + index))
        add(account, "subscription_started", None)
    for index in range(
        6
    ):  # returning customers: paid in March, cancelled, back in July
        account = next(accounts)
        add(account, "signup", at(2, 10 + index))
        add(account, "subscription_started", at(3, 1 + index))
        add(account, "subscription_cancelled", at(5, 1 + index))
        add(account, "subscription_started", at(7, 20 + index))
    return rows


def count(
    rows,
    *,
    zone=LOCAL,
    include_test=False,
    keep_merged=False,
    start_events=("subscription_started",),
    first_only=True,
    distinct=True,
    blanks_in_july=False,
) -> int:
    """July 2026 'new customer' count under one set of definitional choices."""
    seen, firsts, hits = set(), {}, []
    for row in rows:
        key = tuple(row[f] for f in FIELDS)
        if distinct and key in seen:
            continue
        seen.add(key)
        if row["event"] not in start_events or (
            row["is_test"] == "true" and not include_test
        ):
            continue
        if row["merged_into"] and not keep_merged:
            continue
        if not row["occurred_at"]:
            if blanks_in_july:
                hits.append(row["account_id"])
            continue
        local = (
            datetime.strptime(row["occurred_at"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=UTC)
            .astimezone(zone)
        )
        stamp = (local.year, local.month)
        account = row["account_id"]
        if first_only:
            firsts[account] = min(firsts.setdefault(account, stamp), stamp)
        elif stamp == (2026, 7):
            hits.append(account)
    hits.extend(account for account, stamp in firsts.items() if stamp == (2026, 7))
    return len(set(hits)) if distinct else len(hits)


def variants(rows) -> dict:
    """The reference plus one-choice-flipped alternatives; all must differ."""
    result = {
        "reference": count(rows),
        "utc": count(rows, zone=UTC),
        "include_test": count(rows, include_test=True),
        "keep_merged": count(rows, keep_merged=True),
        "trials_count": count(
            rows, start_events=("trial_started", "subscription_started")
        ),
        "signups": count(rows, start_events=("signup",)),
        "any_july_start": count(rows, first_only=False),
        "rows_not_accounts": count(rows, first_only=False, distinct=False),
        "blanks_in_july": count(rows, blanks_in_july=True),
    }
    if len(set(result.values())) != len(result):
        raise ValueError("fixture_variants_collide")
    return result


def write_fixture(folder: Path, rows) -> None:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (folder / "signups.csv").write_text(buffer.getvalue(), encoding="utf-8")
    (folder / "README.md").write_text(README, encoding="utf-8")


def trace(stdout: str) -> dict:
    """Fixed labels and counts from the event stream; no answer text."""
    hooks = tools = ambiguity = analysis = opened = 0
    names: dict[str, int] = {}
    cost = None
    for line in stdout.split("\n"):
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "hook_response":
            hooks += 1
            ambiguity += AMBIGUITY_MARK in str(event.get("stdout", ""))
            analysis += ANALYSIS_MARK in str(event.get("stdout", ""))
        elif kind == "assistant":
            content = (event.get("message") or {}).get("content")
            for item in content if isinstance(content, list) else []:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    tools += 1
                    name = str(item.get("name"))[:40]
                    names[name] = names.get(name, 0) + 1
                    opened += "signups.csv" in json.dumps(item.get("input"))
        elif kind == "result":
            spent = event.get("total_cost_usd")
            if isinstance(spent, (int, float)):
                cost = round(float(spent), 4)
    return {
        "ambiguity_reminders": ambiguity,
        "analysis_reminders": analysis,
        "hook_responses_seen": hooks,
        "tool_calls": tools,
        "tool_calls_by_name": names,
        "fixture_tool_calls": opened,
        "cost_usd": cost,
    }


def communicate_with_trace(command, cwd, env, stdin, timeout) -> dict:
    """host_probe.communicate, adding this eval's trace fields to its parse."""
    original = probe.parse_events

    def parse(stdout, stderr, code):
        return {**original(stdout, stderr, code), **trace(stdout)}

    probe.parse_events = parse
    try:
        return probe.communicate(command, cwd, env, stdin, timeout)
    finally:
        probe.parse_events = original


def session_command(plugin: Path, model: str, effort: str | None) -> list[str]:
    command = [
        shutil.which("claude") or "claude",
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
        "Bash,Read,Grep,Glob",
        "--allowedTools",
        "Bash,Read,Grep,Glob",
        "--no-session-persistence",
        "--model",
        model,
        "--max-budget-usd",
        "2.00",
        "--plugin-dir",
        str(plugin.resolve()),
    ]
    return command + (["--effort", effort] if effort else [])


def run_session(
    prompt: str, plugin: Path, model: str, effort: str | None, timeout: int
) -> dict:
    auth = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        / ".credentials.json"
    )
    with (
        probe._termination_cleanup(),
        tempfile.TemporaryDirectory(prefix="accuracy-ambiguity-") as directory,
    ):
        root = Path(directory)
        profile, work = root / "profile", root / "work"
        profile.mkdir()
        work.mkdir()
        if auth.is_file():
            shutil.copyfile(auth, profile / auth.name)
            (profile / auth.name).chmod(0o600)
        write_fixture(work, make_rows())
        env = {k: v for k, v in os.environ.items() if k not in probe.CONTROL_VARS}
        env["CLAUDE_CONFIG_DIR"] = str(profile)
        stdin = (
            json.dumps({"type": "user", "message": {"role": "user", "content": prompt}})
            + "\n"
        )
        return communicate_with_trace(
            session_command(plugin, model, effort), work, env, stdin, timeout
        )


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-variants",
        action="store_true",
        help="Print the oracle; no model calls.",
    )
    parser.add_argument(
        "--baseline-plugin",
        type=Path,
        help="Released llm-accuracy plugin folder to compare.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        help="Private folder for replies, outside this repository.",
    )
    parser.add_argument("--models", default="claude-sonnet-5-5,claude-opus-5-5")
    parser.add_argument("--prompts", default="vague,precise")
    parser.add_argument("--repeats", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args(arguments)
    oracle = variants(make_rows())
    if args.print_variants:
        print(json.dumps({"fixture_rows": len(make_rows()), "july_counts": oracle}))
        return 0
    if args.baseline_plugin is None or args.raw_dir is None:
        parser.error("a live run needs --baseline-plugin and --raw-dir")
    raw = args.raw_dir.resolve()
    if raw == ROOT or ROOT in raw.parents:
        parser.error("--raw-dir must be outside the repository")
    models = args.models.split(",")
    if not all(probe.MODEL_NAME.fullmatch(model) for model in models):
        parser.error("--models takes model names only")
    prompts = [name for name in args.prompts.split(",") if name in PROMPTS]
    arms = {"current": args.baseline_plugin, "candidate": PLUGIN}
    if not prompts or not all((plugin / HOOK).is_file() for plugin in arms.values()):
        parser.error("unknown prompt set or a plugin without the ambiguity hook")
    raw.mkdir(parents=True, exist_ok=True)
    index = 0
    for model in models:
        for name in prompts:
            for repeat in range(args.repeats):
                order = (
                    ("current", "candidate")
                    if index % 2 == 0
                    else ("candidate", "current")
                )
                index += 1
                for arm in order:
                    result = run_session(
                        PROMPTS[name], arms[arm], model, args.effort, args.timeout
                    )
                    run_id = f"{model}-{name}-{repeat}-{arm}"
                    answers = result.pop("answers", [])
                    (raw / f"{run_id}.md").write_text(
                        "\n\n---\n\n".join(answers), encoding="utf-8"
                    )
                    print(
                        json.dumps(
                            {
                                "run": run_id,
                                "arm": arm,
                                "model": model,
                                "prompt": name,
                                "repeat": repeat,
                                **result,
                            }
                        ),
                        flush=True,
                    )
    print(
        json.dumps(
            {
                "scope": "synthetic_new_customer_count",
                "july_counts": oracle,
                "effort": args.effort or "host_default",
                "repeats": args.repeats,
                "hook_sha256": {
                    arm: hashlib.sha256((plugin / HOOK).read_bytes()).hexdigest()
                    for arm, plugin in arms.items()
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
