#!/usr/bin/env python3
"""Explicit optional experiment: publish and read one coherent two-file report.

Single writer, immutable generations, atomic local os.replace; no fsync promise.
Not a plugin, financial reference, narrative checker, or production storage API.
"""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import uuid
from decimal import Decimal


DOCUMENTS = ("summary.json", "report.csv")


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode("utf-8")


def summarize(source):
    """Demo rule: include issued rows only, summing signed integer AUD cents."""
    balances = {}
    for row in source["invoices"]:
        customer, cents, status = row["customer"], row["cents"], row["status"]
        if (not isinstance(customer, str) or not re.fullmatch(r"C-[0-9]+", customer)
                or type(cents) is not int or status not in ("issued", "cancelled")):
            raise ValueError("Expected C-number customer, integer cents and issued/cancelled status")
        if status == "issued":
            balances[customer] = balances.get(customer, 0) + cents
    return balances


def report_bytes(balances, simulate_empty_failure=False):
    if simulate_empty_failure and not balances:
        raise RuntimeError("simulated report failure after numerical output")
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(("customer", "aud"))
    for customer, cents in sorted(balances.items()):
        sign = "-" if cents < 0 else ""
        writer.writerow((customer, f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"))
    return output.getvalue().encode("utf-8")


def validate(documents):
    """Check table bindings only. Agreement does not prove financial truth."""
    expected = json.loads(documents["summary.json"])
    if (not isinstance(expected, dict)
            or any(not re.fullmatch(r"C-[0-9]+", key) or type(value) is not int
                   for key, value in expected.items())):
        raise ValueError("Unsupported summary")
    rows = csv.reader(io.StringIO(documents["report.csv"].decode("utf-8")), strict=True)
    if next(rows, None) != ["customer", "aud"]:
        raise ValueError("Unsupported report schema; no narrative checked")
    actual = {}
    for row in rows:
        if (len(row) != 2 or row[0] in actual
                or not re.fullmatch(r"[+-]?[0-9]+\.[0-9]{2}", row[1])):
            raise ValueError("Unsupported or duplicate report row")
        actual[row[0]] = Decimal(row[1])
    # Decimal scaling avoids float rounding; input integers are authoritative only
    # for this consistency comparison, not as evidence of source truth.
    if actual != {key: Decimal(f"{'-' if value < 0 else ''}{abs(value) // 100}.{abs(value) % 100:02d}")
                  for key, value in expected.items()}:
        raise ValueError("Customer/amount bindings disagree")


def generation_dir(root, generation):
    if not isinstance(generation, str) or not re.fullmatch(r"[0-9a-f]{32}", generation):
        raise ValueError("Invalid generation identifier")
    return Path(root) / "generations" / generation


def refresh(root, source, simulate_empty_failure=False):
    """Run the producer inside staging, then validate and publish its actual bytes."""
    root = Path(root)
    generation = uuid.uuid4().hex
    folder = generation_dir(root, generation)
    folder.mkdir(parents=True, exist_ok=False)
    balances = summarize(source)
    (folder / "summary.json").write_bytes(json_bytes(balances))
    (folder / "report.csv").write_bytes(report_bytes(balances, simulate_empty_failure))
    documents = {name: (folder / name).read_bytes() for name in DOCUMENTS}
    validate(documents)
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in documents.items()}
    (folder / "manifest.json").write_bytes(json_bytes(hashes))
    pointer = root / (generation + ".pointer")
    pointer.write_bytes(json_bytes({"generation": generation}))
    os.replace(pointer, root / "current.json")
    return generation


def pin(root):
    generation = json.loads((Path(root) / "current.json").read_bytes())["generation"]
    generation_dir(root, generation)
    return generation


def read(root, generation=None):
    """Return both verified documents from one pin, or raise without a result."""
    generation = pin(root) if generation is None else generation
    folder = generation_dir(root, generation)
    hashes = json.loads((folder / "manifest.json").read_bytes())
    if set(hashes) != set(DOCUMENTS):
        raise ValueError("Incomplete manifest")
    documents = {name: (folder / name).read_bytes() for name in DOCUMENTS}
    if any(hashlib.sha256(data).hexdigest() != hashes[name] for name, data in documents.items()):
        raise ValueError("Published bytes changed")
    validate(documents)
    return {"generation": generation, "summary": json.loads(documents["summary.json"]),
            "report": documents["report.csv"].decode("utf-8"),
            "coverage": "One generation; customer/AUD table agreement only. No source truth, freshness or prose check."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    producer = commands.add_parser("refresh")
    producer.add_argument("source", type=Path)
    producer.add_argument("root", type=Path)
    producer.add_argument("--simulate-empty-report-failure", action="store_true")
    consumer = commands.add_parser("read")
    consumer.add_argument("root", type=Path)
    consumer.add_argument("--generation", help="Reuse an earlier pin while its immutable files remain")
    args = parser.parse_args()

    try:
        if args.command == "refresh":
            generation = refresh(args.root, json.loads(args.source.read_bytes()),
                                 args.simulate_empty_report_failure)
            result = {"generation": generation}
        else:
            result = read(args.root, args.generation)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, csv.Error) as error:
        # A refresh error does not imply rollback: after the switch the new
        # generation may be current. Inspect with the supported read command.
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
