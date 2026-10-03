#!/usr/bin/env python3
"""Seal one actual installed-host QA pass into the compatibility candidate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_compatibility import ROOT, TARGETS, code_pass_row, seal_row, validate, write_receipt

BASH_PROOF = {"code-windows-no-bash": "absent", "code-windows-git-bash": "present"}


def sealed_row(options) -> dict:
    if options.target.startswith("code-"):
        if options.bundle_receipt is None:
            raise ValueError("code_pass_requires_bundle_receipt")
        report = json.loads(options.bundle_receipt.read_text(encoding="utf-8"))
        state = BASH_PROOF.get(options.target)
        if state is not None and (not isinstance(report, dict) or report.get("windows_bash") != state):
            raise ValueError("git_bash_proof_mismatch")
        proof = {"git_bash_" + state: True} if state else {}
        return code_pass_row(report, options.target, proof)
    if options.row is None:
        raise ValueError("desktop_pass_requires_row")
    row = json.loads(options.row.read_text(encoding="utf-8"))
    if isinstance(row, dict) and row.get("outcome") == "pass":
        return seal_row(row, row.get("source_commit"))
    raise ValueError("desktop_pass_requires_row")


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--target", choices=TARGETS, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--bundle-receipt",
        type=Path,
        help="claude_bundle_smoke.py receipt from a live run on this Code host",
    )
    source.add_argument(
        "--row", type=Path, help="Desktop UI QA row, including the tested source_commit"
    )
    options = parser.parse_args(arguments)
    path = options.root / "docs/validation/compatibility-candidate.json"
    try:
        row = sealed_row(options)
        receipt = json.loads(path.read_text(encoding="utf-8"))
        receipt["targets"][options.target] = row
        errors = validate(options.root, receipt)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
        label = (
            str(error)
            if isinstance(error, ValueError) and str(error).isidentifier()
            else "invalid_pass_input"
        )
        errors = [label]
    if errors == []:
        try:
            write_receipt(path, receipt)
        except OSError:
            errors = ["candidate_write_failed"]
        except RecursionError:
            errors = ["invalid_pass_input"]
    status = "fail" if errors else "pass"
    print(json.dumps({"status": status, "target": options.target, "errors": errors}))
    return int(status == "fail")


if __name__ == "__main__":
    raise SystemExit(main())
