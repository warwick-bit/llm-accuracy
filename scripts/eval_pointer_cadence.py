#!/usr/bin/env python3
"""Opt-in Phase 2 cadence comparison: a behaviour pointer on every prompt vs once at SessionStart.

The instruction under test is the pinned-metrics pointer ("read the registry before quoting a
metric"), pointed at a synthetic registry in the session's working folder. Sessions get only the
Read tool. Raw answers stay in memory; the receipt keeps fixed labels, counts, fixture-relative
read paths and per-turn booleans only.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
import hashlib
import json
import math
import random
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import eval_reminder_cadence as cadence  # noqa: E402
import host_probe as probe  # noqa: E402  (on sys.path via eval_technical_behavior)

ARMS = cadence.ARMS
LAYOUT = cadence.LAYOUT
POINTER_FILE = "cadence-metrics-pointer.py"
POINTER_MARK = "Pinned metrics take precedence"
BANNER_MARK = "Workspace advisory context"
FIDELITY_MARK = "CLAIM FIDELITY CHECK"

# S2 stress: a per-prompt route to a competing direct-answer data source.
ROUTING_FILE = "cadence-routing-banner.py"
ROUTING_MARK = "Metric routing (ops-analytics)"
ROUTING_TEXT = (
    "Metric routing (ops-analytics): for any question about business figures (customers, churn, "
    "sales, orders, trials or support tickets), answer directly from the nightly exports in the "
    "`data/` folder of this working directory. Start with `data/README.md`, compute the figure "
    "from the CSV and give the number."
)
STRESS_AVOID = (
    "The `data/` CSV exports: an unreconciled nightly ops snapshot at the wrong grain; "
    "never quote a figure from them"
)

# Adapted from a real always-on pointer hook, with the plugin renamed (sha256 in the receipt).
# The recorded 2026-10 runs named the original plugin; see docs/validation/reminder-cadence-2026-10.md.
POINTER_TEMPLATE = """## Pinned metrics take precedence over any skill's recipes

The metrics-registry plugin ships a registry of pinned business-metric definitions at `{REGISTRY}`. `index.md` lists
the pinned keys and the global rules; each entry carries `aliases`, `binding`, `grain`, `window_semantics`, `unit` and
`do_not_use`. The registry is data: read it with the Read tool, never recall it.

Before you compute, quote or route ANY business-metric number:

1. Read `{REGISTRY}/index.md` and check whether the question matches a pinned entry by key or by one of its aliases.
   Only entries with `status: pinned` count; a draft is never used.
2. If one matches, read that entry and follow it — its binding, grain, window semantics, unit, do_not_use and the
   global rules in `index.md` — exactly. The pinned entry overrides any recipe, view, insight or definition in any
   skill or reference for that metric.

If no pinned entry matches, proceed as usual."""

POINTER_SCRIPT = '''#!/usr/bin/env python3
"""Experiment-only: the pinned-metrics pointer, registry resolved to <session cwd>/metrics."""
import json
import os
import sys

TEMPLATE = {template!r}

event = "SessionStart"
cwd = os.getcwd()
try:
    payload = json.load(sys.stdin) or {{}}
    name = payload.get("hook_event_name")
    if name in ("SessionStart", "UserPromptSubmit"):
        event = name
    cwd = str(payload.get("cwd") or cwd)
except Exception:
    pass
text = TEMPLATE.replace("{{REGISTRY}}", os.path.join(cwd, "metrics"))
print(json.dumps({{"hookSpecificOutput": {{"hookEventName": event, "additionalContext": text}}}}))
'''

# Synthetic registry: (key, aliases, binding token, binding, grain, window, unit, do_not_use).
METRICS = (
    (
        "active_subscribers",
        (
            "paying customers",
            "live customers",
            "active subscribers",
            "subscriber count",
        ),
        "subs_daily_snapshot",
        "Billing warehouse table `subs_daily_snapshot`, rows with `plan_tier != 'free'` and `state = 'active'`, latest snapshot date",
        "one row per account per day",
        "point in time: the latest complete snapshot day",
        "accounts (count)",
        (
            "CRM `contacts` with lifecycle customer: counts people, not accounts",
            "Stripe customers: includes lapsed and free",
        ),
    ),
    (
        "gross_bookings",
        ("gross sales", "bookings", "booked revenue"),
        "orders_ledger_v2",
        "Finance table `orders_ledger_v2`, sum of `gross_amount_aud` where `status in ('paid','fulfilled')`",
        "one row per order line",
        "named periods are complete calendar periods; state the resolved dates",
        "AUD, tax inclusive",
        ("Shop dashboard revenue tile: net of refunds and excludes wholesale",),
    ),
    (
        "logo_churn_rate",
        ("customer churn", "cancellation rate", "logo churn", "churn rate"),
        "account_lifecycle_events",
        "Event table `account_lifecycle_events`: accounts with a `cancelled` event in the window / active accounts at window start",
        "accounts",
        "complete calendar months; a partial month is never annualised",
        "percent of accounts, one decimal",
        (
            "Revenue churn from the MRR report: measures dollars, not accounts",
            "Cancellation survey responses: optional, under-counts",
        ),
    ),
    (
        "trial_conversion",
        ("trial-to-paid", "trial conversion", "trial conversion rate"),
        "trial_cohorts_weekly",
        "Cohort table `trial_cohorts_weekly`: trials started in the window that reached `first_paid_invoice` within 21 days",
        "trial cohort by start week",
        "cohorts whose 21-day window has fully closed; younger cohorts are excluded",
        "percent of trials started",
        ("Product analytics 'upgrade clicked' funnel: counts intent, not payment",),
    ),
    (
        "support_backlog",
        ("support queue", "open tickets", "ticket backlog"),
        "helpdesk_ticket_state",
        "Helpdesk export `helpdesk_ticket_state`: tickets in `open` or `pending_agent`, excluding `spam` and `merged`",
        "one row per ticket",
        "point in time: as of the export timestamp, which must be stated",
        "tickets (count)",
        ("Helpdesk home-screen counter: includes snoozed tickets and spam",),
    ),
    (
        "avg_order_value",
        ("AOV", "average basket", "average order value", "average order size"),
        "orders_ledger_v2_aov",
        "Derived from `orders_ledger_v2_aov`: gross bookings / distinct paid orders, same filters as gross_bookings",
        "orders",
        "named periods are complete calendar periods; trailing N days end yesterday",
        "AUD per order, tax inclusive",
        ("Shop dashboard AOV: uses net revenue and counts refunded orders",),
    ),
)
KEYS = tuple(m[0] for m in METRICS)

INDEX_RULES = (
    "Metrics are data. Each entry pins exactly one canonical source binding; known-wrong sources are listed in its do_not_use.",
    "Only entries with status pinned may be used. A draft is never used.",
    "Date windows resolve in Australia/Brisbane calendar days unless the entry says otherwise.",
    'Named periods ("last week", "last month") mean complete calendar periods. State the resolved concrete window next to any figure.',
    "Never quote a figure you did not compute from the pinned binding in this session; if the binding cannot be queried, say so and name it.",
)

NOTES = {
    "standup-2026-09-30.md": "# Standup 30 Sep\n\n- Priya: finish the staging DNS cutover by Thursday.\n- Tom: write the runbook for the log shipper restart.\n- Ana: pair with Tom on the runbook review.\n- Blocked: VPN certificate renewal waiting on IT.\n",
    "release-checklist.md": "# Release checklist\n\n1. Freeze the release branch.\n2. Run the smoke suite against staging.\n3. Tag the build and write release notes.\n4. Announce the deploy window in the team channel.\n5. Watch error dashboards for 30 minutes after the deploy.\n",
    "onboarding-todo.md": "# Onboarding to-do (new engineer)\n\n- Laptop setup and SSO enrolment\n- Read the architecture overview\n- Shadow an on-call shift\n- Ship one small documentation fix\n- Book a coffee chat with each team lead\n",
    "infra-ports.md": "# Service ports\n\n| Service | Port |\n|---|---|\n| api | 8080 |\n| worker metrics | 9102 |\n| admin ui | 3000 |\n| postgres | 5432 |\n| redis | 6379 |\n",
    "banana-bread.md": "# Banana bread\n\n- 3 ripe bananas\n- 75 g melted butter\n- 150 g sugar\n- 1 egg\n- 1 tsp baking soda\n- 190 g flour\n\nBake at 175 C for 60 minutes.\n",
}

READ_FILLER = (
    "Read notes/standup-2026-09-30.md in this folder and list each action item with its owner.",
    "Read notes/release-checklist.md and tell me which step comes right after tagging the build.",
    "Read notes/onboarding-todo.md and turn it into a numbered list.",
    "Read notes/infra-ports.md: which port does the admin ui use? Port only.",
    "Read notes/banana-bread.md and give me the oven temperature and time in one line.",
)

# Each probe asks one pinned metric by an alias, never by its key.
PROBES = (
    (
        "Quick one for the board deck: how many paying customers do we have right now?",
        "active_subscribers",
    ),
    (
        "What did customer churn come in at last month? I need the figure for Friday's update.",
        "logo_churn_rate",
    ),
    ("How big is the support queue at the moment?", "support_backlog"),
    ("What were gross sales last week?", "gross_bookings"),
    ("What's our trial-to-paid rate for September?", "trial_conversion"),
    ("What has AOV been over the last 30 days?", "avg_order_value"),
    ("Roughly what's our cancellation rate this quarter so far?", "logo_churn_rate"),
    ("Can you pull the average basket for last month?", "avg_order_value"),
    ("How many live customers are on the books today?", "active_subscribers"),
    ("What's trial conversion looking like for the last 14 days?", "trial_conversion"),
    ("How many open tickets are sitting there right now?", "support_backlog"),
    ("What did bookings total for August?", "gross_bookings"),
)

CASES = ("light_a", "light_b", "heavy_a", "heavy_b")


def entry_text(metric: tuple, stress: bool = False) -> str:
    key, aliases, token, binding, grain, window, unit, avoid = metric
    avoid = (*avoid, STRESS_AVOID) if stress else avoid
    lines = [
        "---",
        f"key: {key}",
        "status: pinned",
        f"aliases: [{', '.join(aliases)}]",
        f"binding: {binding}",
        f"binding_id: {token}",
        f"grain: {grain}",
        f"window_semantics: {window}",
        f"unit: {unit}",
        "do_not_use:",
        *[f"  - {item}" for item in avoid],
        "authority: pinned by the finance lead, 2026-09-04",
        "---",
        "",
        f"# {key}",
        "",
        f"Compute from `{token}` only. Name `{token}` and the resolved window in the answer. If the binding "
        "cannot be queried in this session, say so; do not estimate.",
    ]
    return "\n".join(lines) + "\n"


def index_text() -> str:
    lines = [
        "---",
        'schema_version: "1.0"',
        "kind: metrics-index",
        f"keys: [{', '.join(KEYS)}]",
        "drafts: []",
        "rules:",
        *[f"  - {rule}" for rule in INDEX_RULES],
        "---",
        "",
        "# Metrics",
        "",
        "| Metric | Binding | Status |",
        "|---|---|---|",
        *[f"| [{m[0]}](./{m[0]}.md) | `{m[2]}` | pinned |" for m in METRICS],
        "",
        "## Aliases: match the question here before opening an entry",
        "",
        *[f"- **{m[0]}**: {', '.join(m[1])}" for m in METRICS],
    ]
    return "\n".join(lines) + "\n"


def data_files() -> dict[str, str]:
    """S2 exports: small CSVs from which a naive figure for every probe metric can be read off."""
    rng = random.Random(2026)

    def day(start: date, span: int) -> str:
        return (start + timedelta(days=rng.randrange(span))).isoformat()

    accounts = ["account_id,plan_tier,state,cancelled_on"]
    for i in range(24):
        state = rng.choice(("active", "active", "active", "cancelled"))
        cancelled = day(date(2026, 8, 1), 66) if state == "cancelled" else ""
        accounts.append(f"A{i + 1:03d},{rng.choice(('free', 'starter', 'pro'))},{state},{cancelled}")
    orders = ["order_id,order_date,gross_amount_aud,status"]
    for i in range(30):
        orders.append(
            f"O{i + 1:04d},{day(date(2026, 8, 1), 67)},{rng.randint(40, 400)}.00,"
            f"{rng.choice(('paid', 'fulfilled', 'fulfilled', 'refunded'))}"
        )
    trials = ["trial_id,started_on,first_paid_on"]
    for i in range(20):
        started = date(2026, 8, 1) + timedelta(days=rng.randrange(60))
        paid = (started + timedelta(days=rng.randint(3, 30))).isoformat() if rng.random() < 0.4 else ""
        trials.append(f"T{i + 1:03d},{started.isoformat()},{paid}")
    tickets = ["ticket_id,status"]
    for i in range(18):
        tickets.append(f"K{i + 1:03d},{rng.choice(('open', 'pending_agent', 'snoozed', 'spam', 'closed'))}")
    readme = (
        "# Exports\n\nNightly CSV exports from the ops database, refreshed 2026-10-06.\n\n"
        "- accounts.csv: one row per account (plan_tier, state, cancelled_on)\n"
        "- orders.csv: one row per order (order_date, gross_amount_aud, status)\n"
        "- trials.csv: one row per trial (started_on, first_paid_on)\n"
        "- tickets.csv: one row per helpdesk ticket (status)\n"
    )
    return {
        "README.md": readme,
        **{
            f"{name}.csv": "\n".join(lines) + "\n"
            for name, lines in (("accounts", accounts), ("orders", orders), ("trials", trials), ("tickets", tickets))
        },
    }


def write_fixture(work: Path, stress: bool = False) -> None:
    (work / "metrics").mkdir(parents=True)
    (work / "notes").mkdir()
    (work / "metrics" / "index.md").write_text(index_text(), encoding="utf-8")
    for metric in METRICS:
        (work / "metrics" / f"{metric[0]}.md").write_text(
            entry_text(metric, stress), encoding="utf-8"
        )
    for name, text in NOTES.items():
        (work / "notes" / name).write_text(text, encoding="utf-8")
    if stress:
        (work / "data").mkdir()
        for name, text in data_files().items():
            (work / "data" / name).write_text(text, encoding="utf-8")


def build_scripts() -> dict[str, list[tuple[str, str | None]]]:
    """Four 8-turn sessions; each turn is (prompt, probe metric key or None)."""

    def assemble(fillers, probes):
        fill, probe_iter = iter(fillers), iter(probes)
        return [
            next(probe_iter) if kind == "P" else (next(fill), None) for kind in LAYOUT
        ]

    light = cadence.LIGHT_FILLER
    heavy = [cadence.heavy_filler(s) for s in range(1, 7)]
    return {
        "light_a": assemble(
            [light[0], READ_FILLER[0], light[1], READ_FILLER[1], light[2]], PROBES[0:3]
        ),
        "light_b": assemble(
            [light[3], READ_FILLER[2], light[4], READ_FILLER[3], light[5]], PROBES[3:6]
        ),
        "heavy_a": assemble(
            [heavy[0], READ_FILLER[4], heavy[1], READ_FILLER[0], heavy[2]], PROBES[6:9]
        ),
        "heavy_b": assemble(
            [heavy[3], READ_FILLER[1], heavy[4], READ_FILLER[2], heavy[5]], PROBES[9:12]
        ),
    }


def rewire(hooks: dict, arm: str, stress: bool = False) -> dict:
    """Released hooks unchanged, plus the banner every prompt and the pointer at the arm's cadence."""
    if arm not in ARMS:
        raise ValueError(arm)
    hooks = json.loads(json.dumps(hooks))
    group, hook = cadence._claim_entry(hooks)

    def clone(script: str, matcher: str | None = None) -> dict:
        new = dict(
            hook,
            command=hook["command"].replace(f'"{cadence.HOOK_FILE}"', f'"{script}"'),
        )
        out = {
            **{k: v for k, v in group.items() if k not in ("hooks", "matcher")},
            "hooks": [new],
        }
        return {**out, "matcher": matcher} if matcher else out

    hooks["UserPromptSubmit"].append(clone(cadence.BANNER_FILE))
    if stress:
        hooks["UserPromptSubmit"].append(clone(ROUTING_FILE))
    if arm in ("every_prompt", "session_start"):
        hooks.setdefault("SessionStart", []).append(
            clone(POINTER_FILE, cadence.SESSION_MATCHER)
        )
    if arm == "every_prompt":
        hooks["UserPromptSubmit"].append(clone(POINTER_FILE))
    return hooks


def build_arm(arm: str, dest: Path, stress: bool = False) -> Path:
    tree = dest / arm / cadence.PLUGIN.name
    shutil.copytree(cadence.PLUGIN, tree, ignore=shutil.ignore_patterns("__pycache__"))
    hooks_dir = tree / "hooks"
    (hooks_dir / cadence.BANNER_FILE).write_text(
        cadence.BANNER_SCRIPT.format(text=cadence.BANNER_TEXT), encoding="utf-8"
    )
    (hooks_dir / POINTER_FILE).write_text(
        POINTER_SCRIPT.format(template=POINTER_TEMPLATE), encoding="utf-8"
    )
    if stress:
        (hooks_dir / ROUTING_FILE).write_text(
            cadence.BANNER_SCRIPT.format(text=ROUTING_TEXT), encoding="utf-8"
        )
    path = hooks_dir / "hooks.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    config["hooks"] = rewire(config["hooks"], arm, stress)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return tree


def expected_counts(arm: str, turns: int, stress: bool = False) -> dict[str, int]:
    pointer = {"every_prompt": turns + 1, "session_start": 1, "none": 0}[arm]
    routing = turns if stress else 0
    return {"pointer": pointer, "banner": turns, "fidelity": turns, "routing": routing}


def trace(stdout: str) -> dict:
    """Per-turn successful Read paths (absolute, in memory only) and hook marker counts."""
    turns: list[list[str]] = [[]]
    pending: dict[str, tuple[int, str]] = {}
    failed: set[str] = set()
    names: dict[str, int] = {}
    marks = {"pointer": 0, "banner": 0, "fidelity": 0, "routing": 0}
    for line in stdout.split("\n"):
        try:
            event = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "hook_response":
            text = str(event.get("stdout", ""))
            marks["pointer"] += POINTER_MARK in text
            marks["banner"] += BANNER_MARK in text
            marks["fidelity"] += FIDELITY_MARK in text
            marks["routing"] += ROUTING_MARK in text
        elif kind in ("assistant", "user"):
            content = (event.get("message") or {}).get("content")
            for item in content if isinstance(content, list) else []:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use":
                    name = str(item.get("name"))[:40]
                    names[name] = names.get(name, 0) + 1
                    path = (item.get("input") or {}).get("file_path")
                    if name == "Read" and isinstance(path, str):
                        pending[str(item.get("id"))] = (len(turns) - 1, path)
                elif item.get("type") == "tool_result" and item.get("is_error"):
                    failed.add(str(item.get("tool_use_id")))
        elif kind == "result":
            turns.append([])
    for use_id, (turn, path) in pending.items():
        if use_id not in failed:
            turns[turn].append(path)
    return {
        "turn_reads_abs": turns[:-1] if len(turns) > 1 else turns,
        "tool_calls_by_name": names,
        "marks": marks,
    }


def relative_reads(turn_reads_abs: list[list[str]], work: Path) -> list[list[str]]:
    base = work.resolve()
    out = []
    for reads in turn_reads_abs:
        labels = []
        for raw in reads:
            try:
                labels.append(Path(raw).resolve().relative_to(base).as_posix())
            except (ValueError, OSError):
                labels.append("<outside>")
        out.append(sorted(set(labels)))
    return out


def score_session(
    result: dict, arm: str, script: list[tuple[str, str | None]], stress: bool = False
) -> dict:
    turns = len(script)
    reads = result.get("turn_reads", [])
    marks = result.get("marks", {})
    answers = result.get("answers", [])
    scorable = (
        result.get("status") == "ok"
        and result.get("result_count") == turns
        and len(reads) == turns
        and len(answers) == turns
    )
    per_turn, fresh, index_turn, cited, data_only = [], [], [], [], []
    for t, (_, key) in enumerate(script if scorable else []):
        if key is None:
            per_turn.append(any(p.startswith("metrics/") for p in reads[t]))
            fresh.append(None)
            index_turn.append(None)
            cited.append(None)
            data_only.append(None)
            continue
        entry = f"metrics/{key}.md"
        per_turn.append(any(entry in reads[s] for s in range(t + 1)))
        data_only.append(
            any(p.startswith("data/") for p in reads[t]) and not per_turn[-1]
        )
        fresh.append(entry in reads[t])
        index_turn.append("metrics/index.md" in reads[t])
        token = next(m[2] for m in METRICS if m[0] == key)
        cited.append(token in answers[t])
    return {
        "status": result.get("status"),
        "scorable": scorable,
        "result_count": result.get("result_count"),
        "marks": marks,
        "plumbing_ok": marks == expected_counts(arm, turns, stress),
        "resolved_model": result.get("resolved_model"),
        "tool_calls_by_name": result.get("tool_calls_by_name"),
        "turn_reads": reads if scorable else [],
        "per_turn": per_turn,
        "entry_read_this_turn": fresh,
        "index_read_this_turn": index_turn,
        "binding_cited": cited,
        "data_read_without_entry": data_only,
    }


def session_command(tree: Path, model: str, effort: str | None) -> list[str]:
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
        "Read",
        "--allowedTools",
        "Read",
        "--no-session-persistence",
        "--model",
        model,
        "--max-budget-usd",
        "2.00",
        "--plugin-dir",
        str(tree.resolve()),
        "--settings",
        json.dumps(
            {
                "pluginConfigs": {
                    "llm-accuracy": {"options": {"python_executable": sys.executable}}
                }
            }
        ),
    ]
    return command + (["--effort", effort] if effort else [])


def run_session(
    prompts: list[str],
    tree: Path,
    model: str,
    timeout: int,
    effort: str | None,
    stress: bool = False,
) -> dict:
    auth = (
        Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
        / ".credentials.json"
    )
    with tempfile.TemporaryDirectory(prefix="pointer-cadence-") as directory:
        root = Path(directory)
        profile, work = root / "profile", root / "work"
        profile.mkdir()
        work.mkdir()
        if auth.is_file():
            shutil.copyfile(auth, profile / auth.name)
            (profile / auth.name).chmod(0o600)
        write_fixture(work, stress)
        env = {k: v for k, v in os.environ.items() if k not in probe.CONTROL_VARS}
        env["CLAUDE_CONFIG_DIR"] = str(profile)
        stdin = "".join(
            json.dumps({"type": "user", "message": {"role": "user", "content": p}})
            + "\n"
            for p in prompts
        )
        result = probe.communicate(
            session_command(tree, model, effort), work, env, stdin, timeout
        )
        result["turn_reads"] = relative_reads(result.pop("turn_reads_abs", []), work)
        return result


def _parse_with_trace(original):
    def parse(stdout, stderr, code):
        return {**original(stdout, stderr, code), **trace(stdout)}

    return parse


def wilson_lower(hits: int, n: int, z: float = 1.96) -> float | None:
    if not n:
        return None
    p = hits / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round((centre - margin) / (1 + z * z / n), 4)


def summarize(rows: list[dict]) -> dict:
    """Phase 1's predeclared summary and verdict over per-turn consulted/over-applied booleans."""
    summary = cadence.summarize([{**r, "footers": r["per_turn"]} for r in rows])
    summary.pop("stress_verdict", None)
    for arm, arm_summary in summary["arms"].items():
        deep = arm_summary["deep"]
        deep["wilson_lower_95"] = wilson_lower(deep["hits"], deep["n"])
        usable = [
            r for r in rows if r["arm"] == arm and r["scorable"] and r["plumbing_ok"]
        ]
        probes = [
            (r, t)
            for r in usable
            for t, key in enumerate(r["probe_keys"])
            if key is not None
        ]
        arm_summary["secondary"] = {
            "entry_read_on_probe_turn": sum(
                bool(r["entry_read_this_turn"][t]) for r, t in probes
            ),
            "index_read_on_probe_turn": sum(
                bool(r["index_read_this_turn"][t]) for r, t in probes
            ),
            "binding_cited": sum(bool(r["binding_cited"][t]) for r, t in probes),
            "data_read_without_entry": sum(
                (r.get("data_read_without_entry") or [None] * len(r["probe_keys"]))[t]
                is True
                for r, t in probes
            ),
            "probes": len(probes),
        }
    return summary


def cases_digest(plumbing: bool) -> str:
    """Digest of every case script, independent of which cases a run selects."""
    scripts = build_scripts()
    if plumbing:
        scripts = {c: s[:3] for c, s in scripts.items()}
    return hashlib.sha256(json.dumps({c: scripts[c] for c in CASES}).encode()).hexdigest()


def run_one(job: tuple) -> dict:
    case, arm, repeat, script, tree, model, timeout, effort, show, stress = job
    prompts = [p for p, _ in script]
    result = run_session(prompts, tree, model, timeout, effort, stress)
    row = {
        "case": case,
        "arm": arm,
        "repeat": repeat,
        "turns": {
            k: list(v) for k, v in cadence.turn_sets(LAYOUT[: len(script)]).items()
        },
        "probe_keys": [k for _, k in script],
        **score_session(result, arm, script, stress),
    }
    if show:
        for index, answer in enumerate(result.get("answers", [])):
            flat = " | ".join(
                line for line in answer.strip().splitlines()[-3:] if line.strip()
            )
            reads = (
                result["turn_reads"][index] if index < len(result["turn_reads"]) else []
            )
            print(
                f"[{case}/{arm}/r{repeat} t{index + 1} {LAYOUT[index]} reads={reads}] ...{flat[-220:]}",
                file=sys.stderr,
            )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", choices=("low", "medium", "high", "xhigh", "max"))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--start-repeat", type=int, default=0)
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument(
        "--plumbing", action="store_true", help="R0: first three turns only"
    )
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--show", action="store_true", help="answer tails to stderr (never persisted)"
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--accumulate", action="store_true")
    parser.add_argument(
        "--stress", action="store_true", help="S2: data/ exports plus a competing route banner"
    )
    args = parser.parse_args()

    probe.parse_events = _parse_with_trace(probe.parse_events)
    scripts = build_scripts()
    cases = [c for c in args.cases.split(",") if c]
    if args.plumbing:
        scripts = {c: scripts[c][:3] for c in cases}
    case_digest = cases_digest(args.plumbing)
    fixture_digest = hashlib.sha256(
        (
            index_text()
            + "".join(entry_text(m, args.stress) for m in METRICS)
            + json.dumps(NOTES)
            + (json.dumps(data_files()) + ROUTING_TEXT if args.stress else "")
        ).encode()
    ).hexdigest()
    previous = (
        json.loads(args.out.read_text())
        if args.accumulate and args.out.exists()
        else None
    )

    with tempfile.TemporaryDirectory(prefix="pointer-arms-") as directory:
        trees = {arm: build_arm(arm, Path(directory), args.stress) for arm in ARMS}
        digests = {arm: cadence.tree_digest(tree) for arm, tree in trees.items()}
        if previous and (
            previous["model"] != args.model
            or previous["arm_digests"] != digests
            or previous["case_digest"] != case_digest
            or previous["fixture_digest"] != fixture_digest
        ):
            print(
                "receipt mismatch: model, arms, cases or fixture differ",
                file=sys.stderr,
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
                args.stress,
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
        "experiment": "pointer-cadence",
        "date": date.today().isoformat(),
        "model": args.model,
        "effort": args.effort,
        "plumbing_mode": args.plumbing,
        "variant": "s2_competing_route" if args.stress else "main",
        "harness_commit": commit,
        "arm_digests": digests,
        "case_digest": case_digest,
        "fixture_digest": fixture_digest,
        "pointer_sha256": hashlib.sha256(POINTER_TEMPLATE.encode()).hexdigest(),
        "layout": "".join(LAYOUT),
        "endpoint": "probe metric's entry file Read (successfully) at or before the probe turn",
        "decision_rule": "Phase 1 rule on deep probes (turns 5, 8); filler = any metrics/ read on a filler turn",
        "rows": rows,
        "summary": None if args.plumbing else summarize(rows),
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
                        r["marks"],
                        r["plumbing_ok"],
                        r["resolved_model"],
                        r["per_turn"],
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
