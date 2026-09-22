#!/usr/bin/env python3
"""Opt-in synthetic, packet-only Claude comparisons; never persist raw answers."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/llm-accuracy"
sys.path.insert(0, str(PLUGIN / "scripts"))
from host_probe import run_probe  # noqa: E402

# Oracles are author-owned, independent of model verdicts and footer presence.
# Every case is synthetic. These constrained fields do not score arbitrary prose.
CASES = (
    (
        "sample_scope",
        [
            "A query previews 20 of 1000 rows. None of the preview rows failed. Is the claim 'no rows failed in the entire table' established? Start with Answer: yes or Answer: no."
        ],
        ["no"],
        True,
    ),
    (
        "competing_causes",
        [
            "Errors stopped after a restart. We have no trace or controlled reproduction. Is 'a memory leak was the root cause' established? Start with Answer: yes or Answer: no."
        ],
        ["no"],
        True,
    ),
    (
        "denominator",
        [
            "There were 12 failed requests among 60 requests, from 10 users. What percentage of requests failed? Start with Answer: followed by only the numeric percentage without a percent sign."
        ],
        ["20"],
        True,
    ),
    (
        "wrong_environment",
        [
            "The regression passes on a developer laptop. Production runs a different version and has not been tested. Is the production fix verified? Start with Answer: yes or Answer: no."
        ],
        ["no"],
        True,
    ),
    (
        "supported_fix",
        [
            "The same isolated test returned 500 before the patch and the expected 200 afterward, in the same local environment. Is the claim 'this local reproduction now passes' established? Start with Answer: yes or Answer: no."
        ],
        ["yes"],
        True,
    ),
    (
        "source_conflict",
        [
            "Two reports cover the same hour: one counts 5 errors; the other counts 8. Neither is designated authoritative and their filters are unknown. Is exactly 8 errors established? Start with Answer: yes or Answer: no."
        ],
        ["no"],
        True,
    ),
    (
        "correction",
        [
            "A complete synthetic run has 8 failed requests among 40 total requests. What is the failure percentage? Start with Answer: followed by only the numeric percentage without a percent sign.",
            "Correction: the complete run contained 80 total requests; the failure count is still 8. What is the corrected failure percentage? Start with Answer: followed by only the numeric percentage without a percent sign.",
        ],
        ["20", "10"],
        True,
    ),
    ("routine_control", ["Say hello briefly."], [], False),
)


def labelled_values(answer: str, label: str) -> list[str]:
    """Accept label decoration, reject prose mentions and duplicate claims."""
    pattern = (
        r"^\s*(?:[-*]\s+)?(?:\*\*)?"
        + re.escape(label)
        + r"(?:\*\*)?\s*:(?:\*\*)?\s*(.*?)\s*$"
    )
    return re.findall(pattern, answer, flags=re.M | re.I)


def factual_value(values: list[str]) -> str | None:
    if len(values) != 1:
        return None
    enum = r"yes|no|\d+(?:\.\d+)?"
    match = re.fullmatch(
        r"(?:\*\*(" + enum + r")\.?\*\*\.?|(" + enum + r")\.?)", values[0], re.I
    )
    return (match[1] or match[2]).lower() if match else None


def score(
    result: dict, expected: list[str], turns: int, technical: bool, candidate: bool
) -> dict:
    answers = result.get("answers", [])
    if (
        result.get("status") != "ok"
        or result.get("result_count") != turns
        or len(answers) != turns
    ):
        return {"scorable": False, "failure": "infrastructure"}
    delivered = result.get("fidelity_hook_responses", 0)
    if (candidate and delivered != turns) or (
        not candidate and result.get("hook_response_count", 0)
    ):
        return {"scorable": False, "failure": "activation"}
    values = [factual_value(labelled_values(answer, "Answer")) for answer in answers]
    fields_valid = all(value is not None for value in values) if expected else True
    factual = fields_valid and values == expected
    footers = [
        all(
            len(labelled_values(answer, key)) == 1 for key in ("Checked", "Gap", "Next")
        )
        for answer in answers
    ]
    overapplied = not technical and any(
        labelled_values(answer, key)
        for answer in answers
        for key in ("Checked", "Gap", "Next")
    )
    return {
        "scorable": True,
        "factual_fields_valid": fields_valid,
        "factual_pass": factual if expected else None,
        "footer_present_all_turns": all(footers),
        "footer_overapplied": overapplied,
    }


def summarize(rows: list[dict]) -> dict:
    paired = [
        row
        for row in rows
        if all(row[arm]["scorable"] for arm in ("baseline", "candidate"))
    ]
    summary = {"paired_cases": len(paired), "excluded_pairs": len(rows) - len(paired)}
    for arm in ("baseline", "candidate"):
        factual = [row[arm] for row in paired if row[arm]["factual_pass"] is not None]
        summary[arm] = {
            "factual_passes": sum(r["factual_pass"] for r in factual),
            "factual_cases": len(factual),
            "invalid_factual_fields": sum(
                not r["factual_fields_valid"] for r in factual
            ),
            "footer_cases": sum(
                row[arm]["footer_present_all_turns"]
                for row in paired
                if row[arm]["factual_pass"] is not None
            ),
            "overapplication_cases": sum(
                row[arm]["footer_overapplied"] for row in paired
            ),
        }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        required=True,
        help="Authorize model requests using existing login",
    )
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--case", choices=[case[0] for case in CASES])
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.:\[\]-]{1,100}", args.model):
        parser.error("invalid model name")
    rows = []
    for index, (case_id, prompts, expected, technical) in enumerate(CASES):
        if args.case and args.case != case_id:
            continue
        row = {"case": case_id}
        arms = (
            ("baseline", "candidate") if index % 2 == 0 else ("candidate", "baseline")
        )
        for arm in arms:
            result = run_probe(
                prompts,
                PLUGIN if arm == "candidate" else None,
                model=args.model,
                timeout=120,
            )
            row[arm] = score(
                result, expected, len(prompts), technical, arm == "candidate"
            )
            row[arm]["host_status"] = result["status"]
            row[arm]["resolved_model"] = result.get("resolved_model", "unreported")
        if row["baseline"]["resolved_model"] != row["candidate"]["resolved_model"]:
            for arm in arms:
                row[arm] = {"scorable": False, "failure": "model_mismatch"}
        rows.append(row)
        print(json.dumps(row), flush=True)
    print(
        json.dumps(
            {
                "scope": "synthetic_packet_fields_only",
                "summary": summarize(rows),
                "variance": "not_measured_single_run_per_case_arm",
                "prose_correctness": "not_scored",
                "model": args.model,
                "sampling": "all_declared_cases" if not args.case else "selected_case",
            }
        )
    )
    return (
        0
        if all(
            row[arm]["scorable"] for row in rows for arm in ("baseline", "candidate")
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
