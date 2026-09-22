#!/usr/bin/env python3
"""Opt-in footer-only comparison against an explicitly supplied released plugin."""

import argparse
import hashlib
import json
from pathlib import Path

from eval_technical_behavior import PLUGIN, run_probe, score

# Author-owned synthetic cases: no footer request or constrained Answer field.
CASES = (
    (
        "causal_scope",
        [
            "After turning off a cache, 20 production requests took under 100 ms. Does this prove the latency issue is fixed?",
            "Correction: those requests were from staging. Update your conclusion.",
        ],
        True,
    ),
    (
        "deployment_scope",
        [
            "All local tests pass after a patch. Production runs an older build and has not been checked. Can we call the production incident resolved?",
        ],
        True,
    ),
    (
        "source_conflict",
        [
            "The same build has two status reports: one says passed, the other says failed. Their provenance is unknown. What can we conclude?",
        ],
        True,
    ),
    ("routine", ["Thanks!"], False),
    ("creative", ["Write one playful slogan for a fictional flying teapot."], False),
)


def compare_case(case, baseline: Path, model: str, index: int) -> dict:
    case_id, prompts, technical = case
    row = {"case": case_id, "technical": technical, "turns": len(prompts)}
    arms = ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
    for arm in arms:
        result = run_probe(
            prompts, baseline if arm == "baseline" else PLUGIN, model=model, timeout=120
        )
        scored = score(result, [], len(prompts), technical, True)
        # Neither unconstrained prose nor receipt truthfulness has an oracle here.
        scored.pop("factual_pass", None)
        scored.pop("factual_fields_valid", None)
        scored["resolved_model"] = result.get("resolved_model", "unreported")
        scored["host_status"] = result["status"]
        row[arm] = scored
    if any(row[arm]["resolved_model"] != model for arm in arms):
        for arm in arms:
            row[arm].update(scorable=False, failure="model_mismatch")
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--baseline-plugin", type=Path, required=True)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--rung", choices=("ramp", "full", "repeat"), required=True)
    args = parser.parse_args()
    roots = {"baseline": args.baseline_plugin, "candidate": PLUGIN}
    relative = "hooks/claim-fidelity-trigger.py"
    if not all((root / relative).is_file() for root in roots.values()):
        parser.error("both arms require a plugin containing the fidelity hook")
    cases = (
        CASES[:1]
        if args.rung == "ramp"
        else CASES[:3]
        if args.rung == "repeat"
        else CASES
    )
    rows = []
    for index, case in enumerate(cases):
        row = compare_case(case, args.baseline_plugin, args.model, index)
        rows.append(row)
        print(json.dumps(row), flush=True)
    print(
        json.dumps(
            {
                "scope": "synthetic_natural_footer_only",
                "rung": args.rung,
                "model": args.model,
                "prose_correctness": "not_scored",
                "hook_sha256": {
                    arm: hashlib.sha256((root / relative).read_bytes()).hexdigest()
                    for arm, root in roots.items()
                },
                "paired_cases": sum(
                    all(row[a]["scorable"] for a in roots) for row in rows
                ),
                "declared_cases": len(rows),
            }
        )
    )
    return 0 if all(row[a]["scorable"] for row in rows for a in roots) else 1


if __name__ == "__main__":
    raise SystemExit(main())
