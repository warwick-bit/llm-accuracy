#!/usr/bin/env python3
"""Read explicit files and check bounded literal equations and digest citations.

No network, subprocesses, discovery, persistence, or edits. JSON goes to stdout.
Exit 0: no bounded objection; 1: discrepancy; 2: unavailable/error.
Source truth and narrative entailment always require separate review.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from saved_output_formulas import check as check_formulas
from saved_output_digests import check as check_digests


def assess(report, version="v3", sources=(), delivery=None, expected_sha256=None):
    if not re.fullmatch(r"v[1-9]\d*", version):
        raise ValueError("Report version must be v followed by a positive integer")
    inputs = {}

    def read(path):
        path = Path(path).resolve(strict=True)
        if path not in inputs:
            inputs[path] = path.read_bytes()
        return path, inputs[path]

    path, raw = read(report)
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256.lower():
        raise ValueError("Report bytes differ from expected SHA-256")
    hashes = {version: digest}
    for label, source in sources:
        if not re.fullmatch(r"v[1-9]\d*", label) or label in hashes:
            raise ValueError("Source versions must be valid and unique")
        _, source_bytes = read(source)
        hashes[label] = hashlib.sha256(source_bytes).hexdigest()
    texts = {"report": raw.decode("utf-8-sig")}
    if delivery is not None:
        _, body = read(delivery)
        texts["delivery"] = body.decode("utf-8-sig")
    formulas = {name: check_formulas(text) for name, text in texts.items()}
    digests = check_digests("\n".join(texts.values()), hashes)
    statuses = [item["status"] for item in formulas.values()] + [digests["status"]]
    status = ("fail" if "fail" in statuses else
              "unavailable" if "unavailable" in statuses else
              "bounded_checks_pass" if "pass" in statuses else "not_applicable")
    for source, original in inputs.items():
        if source.read_bytes() != original:
            raise ValueError("An input changed during checking; rerun on stable files")
    return {"schema": 1, "status": status, "whole_report_status": "unverified",
            "report_sha256": digest, "version_hashes": hashes,
            "input_sha256": {str(p): hashlib.sha256(b).hexdigest() for p, b in inputs.items()},
            "formula_checks": formulas, "digest_checks": digests,
            "limits": ["Checks only supported labelled literal equations and version-labelled SHA-256 citations.",
                       "Source fields, identities, units, history and prose require separate source-bound review.",
                       "Quoted historical equations are preserved; unmarked quotations require attribution review.",
                       "Percentage-valued equations remain outside this checker.",
                       "A matching hash does not establish that an author ran a check."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--version", default="v3")
    parser.add_argument("--source", action="append", default=[], metavar="VERSION=PATH")
    parser.add_argument("--delivery", type=Path)
    parser.add_argument("--expected-sha256")
    args = parser.parse_args()
    try:
        sources = []
        for value in args.source:
            label, separator, path = value.partition("=")
            if not separator or not path:
                raise ValueError("Sources use VERSION=PATH")
            sources.append((label, path))
        result = assess(args.report, args.version, sources, args.delivery, args.expected_sha256)
    except (OSError, ValueError) as error:
        result = {"schema": 1, "status": "unavailable", "whole_report_status": "unverified",
                  "reason": type(error).__name__ + ": " + str(error)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 1 if result["status"] == "fail" else 2 if result["status"] == "unavailable" else 0


if __name__ == "__main__":
    raise SystemExit(main())
