#!/usr/bin/env python3
"""Observe declared files before/after a producer run; never run or repair the producer."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat

from check_numerical_claims import unique_object


def requirements(value):
    if not isinstance(value, dict) or set(value) != {"inputs", "outputs"}:
        raise ValueError("Manifest needs inputs and outputs lists")
    all_paths = []
    for group in ("inputs", "outputs"):
        paths = value[group]
        if not isinstance(paths, list) or not paths:
            raise ValueError("Declare at least one input and output")
        for name in paths:
            if (not isinstance(name, str) or not name or name != name.strip()
                    or "\\" in name or ":" in name or "\x00" in name
                    or PurePosixPath(name).is_absolute()
                    or any(part in ("", ".", "..") or part.endswith((".", " ")) for part in name.split("/"))):
                raise ValueError("Use relative slash-separated file paths without traversal")
        all_paths.extend(paths)
    if len({name.casefold() for name in all_paths}) != len(all_paths):
        raise ValueError("Paths must be unique, disjoint and portable across case-insensitive filesystems")
    return {group: sorted(value[group]) for group in ("inputs", "outputs")}


def observe(root, name):
    path = root / name
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            return {"status": "unavailable"}
        mode = path.stat().st_mode
        if not stat.S_ISREG(mode):
            return {"status": "unavailable"}
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                size += len(chunk)
        return {"status": "readable", "sha256": digest.hexdigest(), "bytes": size}
    except FileNotFoundError:
        return {"status": "missing"}
    except (OSError, ValueError, RuntimeError):
        return {"status": "unavailable"}


def capture(root, spec):
    return {"schema_version": 1, "requirements": spec,
            **{group: {name: observe(root, name) for name in spec[group]} for group in spec}}


def validate_snapshot(before, spec):
    if (not isinstance(before, dict) or set(before) != {"schema_version", "requirements", "inputs", "outputs"}
            or type(before["schema_version"]) is not int or before["schema_version"] != 1
            or requirements(before["requirements"]) != spec):
        raise ValueError("Snapshot does not match the declared requirements")
    for group in ("inputs", "outputs"):
        rows = before[group]
        if not isinstance(rows, dict) or set(rows) != set(spec[group]):
            raise ValueError("Snapshot must retain every declared file")
        for row in rows.values():
            if not isinstance(row, dict):
                raise ValueError("Invalid file observation")
            if row.get("status") == "readable":
                if (set(row) != {"status", "sha256", "bytes"}
                        or not isinstance(row["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
                        or type(row["bytes"]) is not int or row["bytes"] < 0):
                    raise ValueError("Readable observations need byte count and SHA-256")
            elif set(row) != {"status"} or row["status"] not in ("missing", "unavailable"):
                raise ValueError("Invalid file status")


def differences(old, new):
    return [name for name in old if old[name] != new[name]]


def all_readable(rows):
    return all(row["status"] == "readable" for row in rows.values())


def compare(before, after, outcome):
    changed = {group: differences(before[group], after[group]) for group in ("inputs", "outputs")}
    comparable_inputs = all_readable(before["inputs"]) and all_readable(after["inputs"])
    comparable_outputs = all_readable(before["outputs"]) and all_readable(after["outputs"])
    preservation = "not_applicable"
    if outcome == "failed":
        preservation = ("preserved" if not changed["outputs"] else "changed") if comparable_outputs else "not_verified"
        # A missing former output or changed readable output is decisive even if another read failed.
        if any(before["outputs"][name]["status"] == "readable"
               and after["outputs"][name]["status"] in ("readable", "missing") for name in changed["outputs"]):
            preservation = "changed"
    return {"execution": "completed", "declared_run_outcome": outcome,
            "required_outputs": "all_readable" if all_readable(after["outputs"]) else "incomplete_or_unavailable",
            "input_change": ("changed" if changed["inputs"] else "unchanged") if comparable_inputs else "not_verified",
            "output_preservation": preservation, "changed_paths": changed,
            "empty_outputs": [name for name, row in after["outputs"].items() if row.get("bytes") == 0],
            "before": before, "after": after,
            "scope": "Caller-declared outcome; snapshots are not authenticated. Required files and observed bytes only. "
                     "Quiescent local files required; no atomic snapshot, transient-write/crash-safety or semantic-freshness guarantee. "
                     "Unchanged output can be valid after changed input; assess content separately."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("capture", "check"))
    parser.add_argument("root", type=Path, help="Isolated test workspace containing declared inputs and outputs")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--before", type=Path, help="Prior capture JSON, stored outside the declared outputs")
    parser.add_argument("--outcome", choices=("succeeded", "failed"), help="Actual producer outcome observed by the caller")
    args = parser.parse_args()
    if (args.mode == "check") != bool(args.before and args.outcome) or (args.mode == "capture" and (args.before or args.outcome)):
        parser.error("check requires --before and --outcome; capture takes neither")
    try:
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("Root must be a directory")
        spec = requirements(json.loads(args.manifest.read_bytes(), object_pairs_hook=unique_object))
        after = capture(root, spec)
        if args.mode == "capture":
            result = after
        else:
            before_bytes = args.before.read_bytes()
            before = json.loads(before_bytes, object_pairs_hook=unique_object)
            validate_snapshot(before, spec)
            result = compare(before, after, args.outcome)
            result["before_sha256"] = hashlib.sha256(before_bytes).hexdigest()
        print(json.dumps(result, indent=2))
        return 0  # Inspect results: completed execution is not a preservation/accuracy pass.
    except (OSError, ValueError, RecursionError, RuntimeError):
        print(json.dumps({"execution": "error", "error": "Invalid or unavailable manifest, baseline or root"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
