#!/usr/bin/env python3
"""Separate rendering-tolerant follow-up; never rescore the stopped pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import eval_customer_metrics as pilot


def reject_constant(value):
    raise ValueError("nonfinite")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_key")
        result[key] = value
    return result


def score(answer, expected, decision):
    text = answer.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    rendering = "single_fence" if fenced else "bare"
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text, object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, TypeError, RecursionError):
        return {"scorable": False, "failure": "json_decode", "rendering": rendering}
    if not isinstance(value, dict):
        return {"scorable": False, "failure": "root_type", "rendering": rendering}
    required = {"decision", "verified_metrics", "Checked", "Gap", "Next"}
    if set(value) != required:
        return {"scorable": False, "failure": "root_keys", "rendering": rendering}
    result = pilot.score(json.dumps(value), expected, decision)
    if not result["scorable"]:
        result["failure"] = "field_shape"
    return {**result, "rendering": rendering}


def make_prompt(sql, fixture, arm):
    example = {"decision": "supported", "verified_metrics": [], "Checked": "", "Gap": "", "Next": ""}
    return (pilot.make_prompt(sql, fixture, arm)
            + "\nOUTPUT STRUCTURE (example only, not a verdict or answer):\n"
            + json.dumps(example)
            + "\nChoose your own decision. Populate verified_metrics for EVERY customer "
              "using the specified row keys. Put scope and caveats in the JSON string fields. "
              "Do not append a separate evidence footer. A single JSON code fence is accepted.\n")


def run_pair(variant, fixture, model, receipt, output):
    sql = (pilot.EXAMPLE / variant).read_text()
    arms = pilot.ARMS if variant == pilot.VARIANTS[0] else tuple(reversed(pilot.ARMS))
    for arm in arms:
        prompt = make_prompt(sql, fixture, arm)
        result = pilot.run_review(prompt, model)
        fields = ("status", "resolved_model", "result_count", "fidelity_hook_responses",
                  "host_inventory", "successful_fidelity_hooks", "usage_model_matches")
        row = {"variant": variant, "arm": arm, "prompt_sha256": pilot.digest(prompt.encode()),
               "runtime": {key: result.get(key) for key in fields}}
        if pilot.attest(result, model):
            answer = result["answers"][0]
            decision = "supported" if variant == pilot.VARIANTS[0] else "needs_correction"
            row["score"] = score(answer, pilot.expected_rows(fixture), decision)
            row["answer_sha256"] = pilot.digest(answer.encode())
        else:
            row["score"] = {"scorable": False, "failure": "runtime_attestation"}
        receipt["rows"].append(row)
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps({"variant": variant, "arm": arm, **row["score"]}), flush=True)
        if not row["score"]["scorable"]:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", required=True, action="store_true")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; preserve previous receipts.")
    fixture = json.loads((pilot.EXAMPLE / "fixture.json").read_text())
    config = pilot.provenance(args.model)
    config["source_sha256"]["scripts/eval_customer_metrics_v2.py"] = pilot.digest(Path(__file__).read_bytes())
    receipt = {"protocol": "customer_metrics_v2", "config": config, "rows": [], "complete": False}
    for variant in pilot.VARIANTS:
        if not run_pair(variant, fixture, args.model, receipt, args.output):
            return 1
        if variant == pilot.VARIANTS[0] and not all(
                row["score"]["all_scored_fields_correct"] for row in receipt["rows"]):
            receipt["stop_reason"] = "clean_control_quality_failure"
            args.output.write_text(json.dumps(receipt, indent=2) + "\n")
            return 1
    receipt["complete"] = True
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
