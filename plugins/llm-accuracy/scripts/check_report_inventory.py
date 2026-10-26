#!/usr/bin/env python3
"""Bind an explicit assertion inventory to the final report; never certify completeness."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from check_numerical_claims import evaluate_source, unique_object


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_inventory(inventory):
    if (not isinstance(inventory, dict) or set(inventory) != {"assertions"}
            or not isinstance(inventory["assertions"], list)):
        raise ValueError("Inventory needs an assertions list")
    ids, texts = set(), set()
    for item in inventory["assertions"]:
        if (not isinstance(item, dict) or not {"id", "text"} <= set(item)
                or set(item) - {"id", "text", "numerical", "review", "note"}
                or not nonempty(item["id"]) or not nonempty(item["text"])
                or len(item["text"].splitlines()) != 1
                or ("note" in item and not nonempty(item["note"]))):
            raise ValueError("Each assertion needs id and one complete nonblank report line as text")
        text = item["text"].strip()
        if item["id"] in ids or text in texts:
            raise ValueError("Assertion IDs and stripped texts must be unique")
        ids.add(item["id"])
        texts.add(text)
        if "numerical" in item and "review" in item:
            raise ValueError("Choose numerical checking or a recorded manual review")
        if "numerical" in item:
            spec = item["numerical"]
            if (not isinstance(spec, dict) or "source" not in spec
                    or set(spec) - {"source", "csv_mapping"}
                    or not all(nonempty(value) for value in spec.values())):
                raise ValueError("numerical needs a source path and optional csv_mapping path")
        if "review" in item:
            review = item["review"]
            if (not isinstance(review, dict)
                    or set(review) != {"source", "sha256", "assessment", "reason"}
                    or not all(nonempty(value) for value in review.values())
                    or not re.fullmatch(r"[a-f0-9]{64}", review["sha256"])
                    or review["assessment"] not in ("supported", "qualified", "contradicted", "unchecked")):
                raise ValueError("review needs source, lowercase sha256, assessment and reason")


def recorded_review(review, directory):
    result = {"declared_assessment": review["assessment"], "reason": review["reason"],
              "expected_source_sha256": review["sha256"]}
    try:
        raw = (directory / review["source"]).read_bytes()
    except (OSError, ValueError):
        return dict(result, source_binding="unavailable")
    current = digest(raw)
    return dict(result, source_sha256=current,
                source_binding="current" if current == review["sha256"] else "stale")


def check_assertion(item, lines, directory):
    result = {"id": item["id"], "text": item["text"], "report_lines": lines,
              "status": "not_verified"}
    if "note" in item:
        result["note"] = item["note"]
    if not lines:
        return dict(result, report_binding="not_found",
                    reason="Listed text is absent from the final report; reassess changed or removed claims")
    result["report_binding"] = "found"
    if "numerical" in item:
        spec = item["numerical"]
        mapping = directory / spec["csv_mapping"] if "csv_mapping" in spec else None
        checked = evaluate_source(directory / spec["source"], item["text"].strip(), mapping)
        result["numerical"] = checked
        result["status"] = checked["claims"][0]["status"]
    elif "review" in item:
        result["review"] = recorded_review(item["review"], directory)
        result["reason"] = "Manual assessment recorded; source freshness is checked, semantic support is not"
    else:
        result["reason"] = "No evidence check supplied"
    return result


def check_inventory(report, inventory, directory):
    validate_inventory(inventory)
    lines = [{"line": number, "text": text} for number, text in enumerate(report.splitlines(), 1) if text.strip()]
    by_text = {}
    for line in lines:
        by_text.setdefault(line["text"].strip(), []).append(line["line"])
    results = [check_assertion(item, by_text.get(item["text"].strip(), []), directory)
               for item in inventory["assertions"]]
    by_line = {line: item for item in results for line in item["report_lines"]}
    for line in lines:
        item = by_line.get(line["line"])
        line.update(assertion_id=item["id"] if item else None,
                    status=item["status"] if item else "not_verified")
    unlisted = [line for line in lines if line["assertion_id"] is None]
    return {"execution": "completed", "assertions": results, "report_lines": lines,
            "unlisted_lines": unlisted, "missing_assertions": [item["id"] for item in results if not item["report_lines"]],
            "coverage": {"nonblank_lines": len(lines), "listed_lines": len(lines) - len(unlisted),
                         "unlisted_lines": len(unlisted), "semantic_completeness": "not_verified"},
            "scope": "Exact complete lines, ignoring outer whitespace. All nonblank lines retained, including headings. "
                     "No automatic claim extraction, compound-claim decomposition or whole-report truth verdict. "
                     "Numerical results inherit supplied definitions; manual assessments are not machine verification."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path, help="Final delivered UTF-8 text or Markdown report")
    parser.add_argument("inventory", type=Path, help="Explicit assertion inventory JSON; paths resolve beside it")
    args = parser.parse_args()
    try:
        report, inventory = args.report.read_bytes(), args.inventory.read_bytes()
        result = check_inventory(report.decode("utf-8-sig"),
                                 json.loads(inventory, object_pairs_hook=unique_object), args.inventory.parent)
        result["sha256"] = {"report": digest(report), "inventory": digest(inventory),
                            "checker": digest(Path(__file__).read_bytes())}
    except (OSError, ValueError, RecursionError):
        print(json.dumps({"execution": "error", "error": "Report or inventory unavailable or invalid"}))
        return 2
    print(json.dumps(result, indent=2))
    return 0  # Completed execution is not an accuracy/completeness pass.


if __name__ == "__main__":
    raise SystemExit(main())
