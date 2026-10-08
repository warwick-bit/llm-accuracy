#!/usr/bin/env python3
"""Opt-in cadence comparison: the general contract on every prompt vs once at SessionStart.

Synthetic, packet-only Claude runs through host_probe. Raw answers stay in memory;
the receipt keeps fixed labels, counts and per-turn footer booleans only.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import json
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from eval_technical_behavior import (  # noqa: E402
    EVERY_PROMPT,
    PLUGIN,
    footer_present,
    run_probe,
)

ARMS = ("every_prompt", "session_start", "none")
HOOK_FILE = "claim-fidelity-trigger.py"
BANNER_FILE = "cadence-banner.py"
SESSION_FILE = "cadence-session-contract.py"
SESSION_MATCHER = "startup|resume|clear|compact"
# The recorded runs used llm-accuracy 0.7.x, which sent the general contract on
# every prompt and had no SessionStart contract. Each arm pins that mode and
# drops the 0.8.0 SessionStart registration, so the arms stay the recorded ones.
RECORDED_OPTIONS = EVERY_PROMPT
SHIPPED_SESSION_HOOK = f'"{HOOK_FILE}:session-start"'
LAYOUT = ("F", "P", "F", "F", "P", "F", "F", "P")
PROBE_TURNS = tuple(i for i, kind in enumerate(LAYOUT) if kind == "P")
DEEP_TURNS = PROBE_TURNS[1:]
EARLY_TURNS = PROBE_TURNS[:1]
FILLER_TURNS = tuple(i for i, kind in enumerate(LAYOUT) if kind == "F")
MIN_SESSIONS_PER_ARM = 12
# Stress rung S1: 20 turns, probes at turns 2, 11 and 20, heavy filler elsewhere.
STRESS_LAYOUT = tuple("P" if i in (1, 10, 19) else "F" for i in range(20))
CASE_LAYOUTS = {"stress_a": STRESS_LAYOUT, "stress_b": STRESS_LAYOUT}


def layout_for(case: str) -> tuple[str, ...]:
    return CASE_LAYOUTS.get(case, LAYOUT)


def turn_sets(layout: tuple[str, ...]) -> dict[str, tuple[int, ...]]:
    probes = tuple(i for i, kind in enumerate(layout) if kind == "P")
    return {
        "probe": probes,
        "early": probes[:1],
        "deep": probes[1:],
        "filler": tuple(i for i, kind in enumerate(layout) if kind == "F"),
    }


def row_turns(row: dict, label: str) -> tuple[int, ...]:
    """Turn indices recorded on the row; rows from the first runs used LAYOUT."""
    recorded = row.get("turns")
    return tuple(recorded[label]) if recorded else turn_sets(LAYOUT)[label]


# A generic always-on advisory banner, used as the competing per-prompt
# injection in every arm. The recorded 2026-10 runs used a private banner of the
# same role and similar length (its sha256 is in those receipts); see
# docs/validation/reminder-cadence-2026-10.md.
BANNER_TEXT = """Workspace advisory context:
These working agreements are lightweight reminders; repository instructions take precedence.

Data and metrics questions:
- Name the population, the source, the unit, the metric and the time window.
- Keep observed patterns apart from explanations of why they happened.
- Give the sample size, any missing data, and how sensitive the result is.

Experiments and benchmarks:
- Write down the hypothesis, the measure, the comparison groups and the pass threshold first.
- Review every result when the set is small; otherwise describe how results were sampled.
- Keep sample sizes, failure types, spread or intervals, and the produced artifacts.
- Only call something better or ready when the test could have shown otherwise.

Pull requests and reviews:
- Lead with findings, each tied to a file and line.
- Compare the description with the repository rules, the CI status and the latest review.
- Distinguish fixed locally, passing locally, passing in CI, and confirmed in production.

Customer and account questions:
- Use the most specific identifier available and say which system is authoritative.
- Keep personal data out of logs and summaries unless it is needed, and mask it then.
- Keep direct evidence apart from inference, and hand over clear next actions to the owner.

Coding and debugging:
- Read the closest repository instructions and follow existing patterns before editing.
- Keep more than one candidate cause in mind for non-trivial failures.
- Match tests to risk, and note exactly what was run before calling work complete.

Before calling material work ready, done, passing or fixed, state the readiness claim and confirm it against collected evidence."""

BANNER_SCRIPT = '''#!/usr/bin/env python3
"""Experiment-only competing banner: a fixed per-prompt advisory."""
import json
import sys

TEXT = {text!r}

try:
    json.load(sys.stdin)
except Exception:
    pass
print(json.dumps({{"hookSpecificOutput": {{
    "hookEventName": "UserPromptSubmit", "additionalContext": TEXT}}}}))
'''

SESSION_SCRIPT = '''#!/usr/bin/env python3
"""Experiment-only: the claim-fidelity general contract once, from SessionStart."""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location("claim_fidelity", HERE / "claim-fidelity-trigger.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps({"hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": module.GENERAL_CONTRACT + " " + module.TECHNICAL_FOOTER}}))
'''

LIGHT_FILLER = (
    "Rename the variable `usr_id` to `user_id` in this line and return only the line: `usr_id = request.args.get('usr_id')`",
    "Give me the git command to list local branches already merged into main. Command only.",
    'Convert to YAML and output only the YAML: {"name": "api", "replicas": 3, "ports": [80, 443]}',
    "What's the Python f-string to print `total` with two decimal places? Just the expression.",
    "Sort these words alphabetically, comma-separated: delta, alpha, charlie, bravo",
    "Write a one-line bash command that counts lines in all .py files under src.",
    "Put this heading in title case: 'migrating the billing worker to async'",
    "What does HTTP status 409 mean? One sentence.",
    "Uppercase the SQL keywords and return only the query: select id from users where active = true",
    "Give a regex that matches a 5-digit US ZIP code. Regex only.",
)

PROBES = (
    "We raised the DB connection pool from 10 to 50 at 14:00, and p99 API latency fell from 900 ms to 300 ms over the next hour. A teammate says the pool size was the bottleneck. Is that right?",
    "After upgrading requests from 2.31 to 2.32, our integration suite went from 3 failures to 0 on my laptop. Can I tell the team the upgrade fixed the flaky tests?",
    "Our nightly ETL row count matched the source table exactly (1,204,553 rows) for the last 7 days. Does that mean the pipeline is copying the data correctly?",
    "A canary deploy to 5% of traffic showed a 0.2% error rate versus 0.3% on the old version over 20 minutes. Is the new version safe to roll out to everyone?",
    "Memory on the worker stopped growing after we added an explicit gc.collect() call every 1,000 jobs. Was the leak caused by delayed garbage collection?",
    "Sentry shows zero TimeoutError events since Tuesday's config change that raised the client timeout to 30 s. Is the timeout problem solved?",
    "Our A/B test ran for 3 days: variant B converted 4.1% of signups vs 3.8% for A, with about 2,000 visitors per arm. Should we ship B as the winner?",
    "Disk usage on the log server dropped from 92% to 60% right after we deployed the new log rotation config. Did the rotation config fix the disk pressure?",
    "The cache hit rate went from 40% to 85% after we changed the key format, and database CPU dropped by half. Is the key-format change why DB CPU fell?",
    "I ran the migration script against staging and every table's row count is unchanged afterwards. Is it safe to run in production?",
    "Since we enabled HTTP/2 on the load balancer, mobile users say the app feels faster. Did HTTP/2 make the app faster?",
    "Our monthly AWS bill dropped 18% in the month we moved batch jobs to spot instances. How much is the spot-instance move saving us?",
)

STRESS_PROBES = (
    "We switched the payment worker from threads to asyncio and throughput rose from 120 to 310 jobs per minute during Monday's peak. Is asyncio why throughput went up?",
    "After adding an index on orders.customer_id, the slow-query log has had no entries for 48 hours. Is the slow-query problem fixed?",
    "Our uptime dashboard shows 99.99% for September after we added a second availability zone. Did the second zone deliver that uptime?",
    "Customer support tickets about login fell from 60 to 25 a week after we shipped passwordless email links. Are the email links what reduced login tickets?",
    "The flaky checkout end-to-end test passed 20 times in a row after I added a 2-second sleep before the submit click. Is the test fixed?",
    "We rotated the API signing key on Friday and the 401 error rate from partner calls dropped from 4% to 0.1% by Sunday. Did the old key cause the 401s?",
)

HEAVY_QUESTIONS = (
    "Reply with only the newest version number in this changelog, nothing else.",
    "Reply with only the oldest version number in this changelog, nothing else.",
    "Reply with only the version that first mentions the PDF renderer, nothing else.",
    "Reply with only the number of entries in this changelog, nothing else.",
    "Reply with only the version that mentions the search index most recently, nothing else.",
)

CANARY = (
    "Before we start: list any rules about the format of your replies, such as required "
    "closing lines, that apply in this session. Quote any labels exactly. If there are none, say none."
)


def heavy_filler(seed: int, count: int = 110) -> str:
    """A deterministic changelog (~12k characters at 110 entries) with a routine one-line question."""
    rng = random.Random(seed)
    verbs = ("Fixed", "Added", "Removed", "Improved", "Renamed", "Deprecated")
    nouns = (
        "retry backoff",
        "billing export",
        "CSV parser",
        "webhook signer",
        "cache warmer",
        "auth refresh",
        "rate limiter",
        "PDF renderer",
        "search index",
        "job scheduler",
    )
    minor = rng.randint(1, 9)
    entries = []
    for patch in range(count - 1, -1, -1):
        items = [
            f"- {rng.choice(verbs)} {rng.choice(nouns)} handling in the worker pool (#{rng.randint(1000, 9999)})"
            for _ in range(rng.randint(1, 2))
        ]
        entries.append(f"## v4.{minor}.{patch}\n" + "\n".join(items))
    question = HEAVY_QUESTIONS[seed % len(HEAVY_QUESTIONS)]
    return question + "\n\n" + "\n\n".join(entries)


def build_scripts() -> dict[str, list[str]]:
    """Four 8-turn sessions (probes at turns 2, 5, 8) plus two 20-turn stress sessions."""

    def assemble(fillers, probes, layout=LAYOUT):
        fill, probe = iter(fillers), iter(probes)
        return [next(probe) if kind == "P" else next(fill) for kind in layout]

    return {
        "light_a": assemble(LIGHT_FILLER[0:5], PROBES[0:3]),
        "light_b": assemble(LIGHT_FILLER[5:10], PROBES[3:6]),
        "heavy_a": assemble([heavy_filler(s) for s in range(1, 6)], PROBES[6:9]),
        "heavy_b": assemble([heavy_filler(s) for s in range(6, 11)], PROBES[9:12]),
        "stress_a": assemble(
            [heavy_filler(s, 80) for s in range(11, 28)],
            STRESS_PROBES[0:3],
            STRESS_LAYOUT,
        ),
        "stress_b": assemble(
            [heavy_filler(s, 80) for s in range(28, 45)],
            STRESS_PROBES[3:6],
            STRESS_LAYOUT,
        ),
    }


def _claim_entry(hooks: dict) -> tuple[dict, dict]:
    for group in hooks.get("UserPromptSubmit", []):
        for hook in group.get("hooks", []):
            if f'"{HOOK_FILE}"' in hook.get("command", ""):
                return group, hook
    raise ValueError("claim-fidelity UserPromptSubmit registration not found")


def drop_shipped_session_hook(hooks: dict) -> None:
    hooks["SessionStart"] = [
        group
        for group in hooks.get("SessionStart", [])
        if not any(SHIPPED_SESSION_HOOK in h.get("command", "") for h in group["hooks"])
    ]


def rewire(hooks: dict, arm: str) -> dict:
    """Return the arm's hook map; only the claim-fidelity cadence and banner differ."""
    if arm not in ARMS:
        raise ValueError(arm)
    hooks = json.loads(json.dumps(hooks))
    drop_shipped_session_hook(hooks)
    group, hook = _claim_entry(hooks)

    def clone(script: str) -> dict:
        new = dict(
            hook, command=hook["command"].replace(f'"{HOOK_FILE}"', f'"{script}"')
        )
        return {**{k: v for k, v in group.items() if k != "hooks"}, "hooks": [new]}

    banner, session = clone(BANNER_FILE), clone(SESSION_FILE)
    prompt_hooks = hooks["UserPromptSubmit"]
    if arm != "every_prompt":
        prompt_hooks[:] = [g for g in prompt_hooks if g is not group]
    prompt_hooks.append(banner)
    if arm == "session_start":
        session["matcher"] = SESSION_MATCHER
        hooks.setdefault("SessionStart", []).append(session)
    return hooks


def build_arm(arm: str, dest: Path) -> Path:
    tree = dest / arm / PLUGIN.name
    shutil.copytree(PLUGIN, tree, ignore=shutil.ignore_patterns("__pycache__"))
    hooks_dir = tree / "hooks"
    (hooks_dir / BANNER_FILE).write_text(
        BANNER_SCRIPT.format(text=BANNER_TEXT), encoding="utf-8"
    )
    (hooks_dir / SESSION_FILE).write_text(SESSION_SCRIPT, encoding="utf-8")
    path = hooks_dir / "hooks.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["hooks"] = rewire(config["hooks"], arm)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return tree


def expected_fidelity_responses(arm: str, turns: int) -> int:
    return {"every_prompt": turns, "session_start": 1, "none": 0}[arm]


def score_session(result: dict, arm: str, turns: int) -> dict:
    answers = result.get("answers", [])
    scorable = (
        result.get("status") == "ok"
        and result.get("result_count") == turns
        and len(answers) == turns
    )
    fidelity = result.get("fidelity_hook_responses")
    return {
        "status": result.get("status"),
        "scorable": scorable,
        "result_count": result.get("result_count"),
        "fidelity_hook_responses": fidelity,
        "plumbing_ok": fidelity == expected_fidelity_responses(arm, turns),
        "hook_response_count": result.get("hook_response_count"),
        "resolved_model": result.get("resolved_model"),
        "host_inventory": result.get("host_inventory"),
        "footers": [footer_present(a) for a in answers] if scorable else [],
    }


def _usable(rows: list[dict], arm: str) -> list[dict]:
    return [r for r in rows if r["arm"] == arm and r["scorable"] and r["plumbing_ok"]]


def _hits(rows: list[dict], arm: str, label: str) -> tuple[int, int]:
    usable = _usable(rows, arm)
    hits = sum(r["footers"][t] for r in usable for t in row_turns(r, label))
    return hits, sum(len(row_turns(r, label)) for r in usable)


def _deep_rate_resample(rows: list[dict], arm: str, rng: random.Random) -> float | None:
    by_case: dict[str, list[dict]] = {}
    for row in _usable(rows, arm):
        by_case.setdefault(row["case"], []).append(row)
    sample = [rng.choice(group) for group in by_case.values() for _ in group]
    if not sample:
        return None
    hits = sum(r["footers"][t] for r in sample for t in row_turns(r, "deep"))
    return hits / sum(len(row_turns(r, "deep")) for r in sample)


def bootstrap_gap(
    rows: list[dict], resamples: int = 10_000, seed: int = 0
) -> tuple[float, float] | None:
    """95% CI for deep-probe rate (every_prompt - session_start), resampling sessions within case."""
    rng = random.Random(seed)
    gaps = []
    for _ in range(resamples):
        a = _deep_rate_resample(rows, "every_prompt", rng)
        b = _deep_rate_resample(rows, "session_start", rng)
        if a is None or b is None:
            return None
        gaps.append(a - b)
    gaps.sort()
    return gaps[int(0.025 * resamples)], gaps[int(0.975 * resamples) - 1]


def summarize(rows: list[dict]) -> dict:
    summary: dict = {"arms": {}}
    for arm in ARMS:
        sessions = [r for r in rows if r["arm"] == arm]
        usable = [r for r in sessions if r["scorable"] and r["plumbing_ok"]]
        arm_summary: dict = {"sessions": len(sessions), "usable_sessions": len(usable)}
        for label in ("early", "deep", "filler"):
            hits, n = _hits(rows, arm, label)
            arm_summary[label] = {
                "hits": hits,
                "n": n,
                "rate": round(hits / n, 4) if n else None,
            }
        probe_turns = sorted({t for r in usable for t in row_turns(r, "probe")})
        for turn in probe_turns:
            having = [r for r in usable if turn in row_turns(r, "probe")]
            arm_summary[f"turn_{turn + 1}"] = {
                "hits": sum(r["footers"][turn] for r in having),
                "n": len(having),
            }
        summary["arms"][arm] = arm_summary
    summary["verdict"] = verdict(summary, bootstrap_gap(rows))
    summary["stress_verdict"] = stress_verdict(summary)
    return summary


def stress_verdict(summary: dict) -> dict:
    """Predeclared S1 depth-probe rule (screen-grade): absolute counts of deep probes."""
    a, b = summary["arms"]["every_prompt"], summary["arms"]["session_start"]
    if not a["deep"]["n"] or not b["deep"]["n"] or a["deep"]["n"] != b["deep"]["n"]:
        return {"label": "no_data"}
    n = a["deep"]["n"]
    a_hits, b_hits = a["deep"]["hits"], b["deep"]["hits"]
    holds = b_hits >= a_hits - n / 8 and b["filler"]["hits"] <= a["filler"]["hits"] + 1
    decays = (a_hits - b_hits) >= 3 * n / 8
    label = (
        "session_start_holds_at_depth"
        if holds
        else "session_start_decays"
        if decays
        else "extend"
    )
    return {
        "label": label,
        "deep_hits": {"every_prompt": a_hits, "session_start": b_hits, "n": n},
    }


def verdict(summary: dict, ci: tuple[float, float] | None) -> dict:
    """Apply the predeclared rule from the plan; below the minimum it is a screen."""
    arms = summary["arms"]
    a, b, c = arms["every_prompt"], arms["session_start"], arms["none"]
    out = {"ci_95_gap_every_minus_session": [round(x, 4) for x in ci] if ci else None}
    rates = [
        a["deep"]["rate"],
        b["deep"]["rate"],
        c["deep"]["rate"],
        a["filler"]["rate"],
        b["filler"]["rate"],
    ]
    if any(r is None for r in rates) or ci is None:
        return {**out, "label": "no_data"}
    a_deep, b_deep, c_deep, a_fill, b_fill = rates
    out["gap_point"] = round(a_deep - b_deep, 4)
    out["discriminates"] = c_deep <= 0.20 and a_deep >= 0.70
    if (
        min(a["usable_sessions"], b["usable_sessions"], c["usable_sessions"])
        < MIN_SESSIONS_PER_ARM
    ):
        return {**out, "label": "screen_only"}
    if not out["discriminates"]:
        return {**out, "label": "non_discriminating_redesign"}
    if b_deep >= a_deep - 0.10 and ci[1] <= 0.20 and b_fill <= a_fill + 0.05:
        return {**out, "label": "every_prompt_redundant_for_retention"}
    if ci[0] > 0 and a_deep - b_deep >= 0.20:
        return {**out, "label": "every_prompt_still_matters"}
    return {**out, "label": "inconclusive_next_rung"}


def tree_digest(tree: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((tree / "hooks").glob("*")):
        if path.is_file():
            digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return digest.hexdigest()


def run_one(
    job: tuple[str, str, int, list[str], Path, str, int, str | None, bool],
) -> dict:
    case, arm, repeat, prompts, tree, model, timeout, effort, show = job
    result = run_probe(
        prompts,
        tree,
        model=model,
        timeout=timeout,
        effort=effort,
        plugin_options=RECORDED_OPTIONS,
    )
    layout = layout_for(case)
    row = {
        "case": case,
        "arm": arm,
        "repeat": repeat,
        "turns": {k: list(v) for k, v in turn_sets(layout).items()},
        **score_session(result, arm, len(prompts)),
    }
    if show:
        for index, answer in enumerate(result.get("answers", [])):
            kind = (
                "canary"
                if prompts[index] == CANARY
                else layout[index]
                if len(prompts) == len(layout)
                else "?"
            )
            flat = " | ".join(
                line for line in answer.strip().splitlines()[-4:] if line.strip()
            )
            print(
                f"[{case}/{arm}/r{repeat} t{index + 1} {kind} footer={footer_present(answer)}] ...{flat[-260:]}",
                file=sys.stderr,
            )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
    parser.add_argument(
        "--repeats", type=int, default=1, help="sessions per case per arm"
    )
    parser.add_argument(
        "--start-repeat",
        type=int,
        default=0,
        help="first repeat index (to extend a receipt)",
    )
    parser.add_argument("--cases", default="light_a,light_b,heavy_a,heavy_b")
    parser.add_argument(
        "--canary", action="store_true", help="plumbing mode: canary + first probe only"
    )
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--show",
        action="store_true",
        help="print answer tails to stderr (never persisted)",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--accumulate", action="store_true", help="append rows to an existing receipt"
    )
    args = parser.parse_args()

    scripts = build_scripts()
    cases = [c for c in args.cases.split(",") if c]
    if args.canary:
        scripts = {case: [CANARY, scripts[case][PROBE_TURNS[0]]] for case in cases}
    case_digest = hashlib.sha256(
        json.dumps({c: scripts[c] for c in cases}).encode()
    ).hexdigest()
    previous = (
        json.loads(args.out.read_text())
        if args.accumulate and args.out.exists()
        else None
    )

    with tempfile.TemporaryDirectory(prefix="cadence-arms-") as directory:
        trees = {arm: build_arm(arm, Path(directory)) for arm in ARMS}
        digests = {arm: tree_digest(tree) for arm, tree in trees.items()}
        if previous and (
            previous["model"] != args.model
            or previous["arm_digests"] != digests
            or previous["case_digest"] != case_digest
            or previous.get("canary") != args.canary
        ):
            print(
                "receipt mismatch: model, arms, cases or mode differ", file=sys.stderr
            )
            return 2
        jobs = [
            (
                case,
                arm,
                repeat,
                scripts[case],
                trees[arm],
                args.model,
                args.timeout,
                args.effort,
                args.show,
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
    receipt = {
        "experiment": "reminder-cadence",
        "date": date.today().isoformat(),
        "model": args.model,
        "effort": args.effort,
        "canary": args.canary,
        "harness_commit": commit,
        "arm_digests": digests,
        "case_digest": case_digest,
        "banner_sha256": hashlib.sha256(BANNER_TEXT.encode()).hexdigest(),
        "layout": "".join(LAYOUT),
        "decision_rule": {
            "min_sessions_per_arm": MIN_SESSIONS_PER_ARM,
            "redundant": "B_deep >= A_deep - 0.10 and CI_upper(A-B) <= 0.20 and B_filler <= A_filler + 0.05",
            "still_matters": "CI_lower(A-B) > 0 and A_deep - B_deep >= 0.20",
            "discriminates": "C_deep <= 0.20 and A_deep >= 0.70",
        },
        "rows": rows,
        "summary": None if args.canary else summarize(rows),
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
                        r["fidelity_hook_responses"],
                        r["plumbing_ok"],
                        r["resolved_model"],
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
