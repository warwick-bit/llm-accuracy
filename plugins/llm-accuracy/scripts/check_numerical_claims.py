#!/usr/bin/env python3
"""Check bounded whole-line monetary metric claims against a supplied snapshot.

No model, automatic claim extraction or source authentication.
Exit 0 means execution completed; inspect each claim's status, not the exit code.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re


PERIOD = r"[1-9][0-9]{3}-(?:0[1-9]|1[0-2])"
WINDOW = rf" from (?P<before>{PERIOD}) to (?P<after>{PERIOD}) in (?P<currency>[A-Z]{{3}})\.?"
METRIC = r"[A-Z][A-Z0-9 _/-]{0,79}?"
PERCENT = r"(?P<percent>[+-]?[0-9]+(?:\.[0-9]{1,2})?)%"
GROWTH = re.compile(rf"Total (?P<metric>{METRIC}) growth was " + PERCENT + WINDOW, re.I)
EVERY = re.compile(rf"(?P<metric>{METRIC}) increased for every region" + WINDOW, re.I)
RATIO = re.compile(rf"(?P<metric>{METRIC}) was " + PERCENT + WINDOW, re.I)


def unique_object(pairs):
    """Do not let JSON silently replace an earlier region, period or definition."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; source is ambiguous")
        result[key] = value
    return result


def selected_values(source, before, after, currency, metric, ratio=False):
    declared = source.get("metric") if isinstance(source, dict) else None
    if (not isinstance(declared, str) or not re.fullmatch(METRIC, declared, re.I)
            or " ".join(declared.split()).casefold() != metric.casefold()):
        raise ValueError("Claim metric must match the source's explicit metric name")
    if source.get("currency") != currency:
        raise ValueError("Claim currency does not match the source currency")
    if before >= after:
        raise ValueError("Comparison needs two distinct periods in chronological order")
    population = source.get("population")
    if (not isinstance(population, list) or not population
            or not all(isinstance(region, str) and region.strip() == region and region
                       for region in population)
            or len(set(population)) != len(population)):
        raise ValueError("Source needs a nonempty, unique declared region population")
    periods = source.get("values_cents")
    selected = [(periods, before), (periods, after)]
    if ratio:
        definition, series = source.get("ratio"), source.get("series_cents")
        if not isinstance(definition, dict) or not isinstance(series, dict):
            raise ValueError("Ratio needs named numerator/denominator and series_cents")
        names = [definition.get(key) for key in ("denominator", "numerator")]
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("Ratio needs explicit numerator and denominator series names")
        selected = [(series.get(names[0]), before), (series.get(names[1]), after)]
    values = []
    for periods, period in selected:
        if not isinstance(periods, dict):
            raise ValueError("Missing monetary values by period")
        rows = periods.get(period)
        if not isinstance(rows, dict) or set(rows) != set(population):
            raise ValueError("Missing or extra region values for " + period)
        if any(type(value) is not int for value in rows.values()):
            raise ValueError("Monetary values must be signed integer cents")
        values.append(rows)
    return population, values[0], values[1]


def ratio_percent(numerator, denominator, places):
    """Exact percentage rounding, ties away from zero; denominator must be positive."""
    scaled_change = numerator * 100 * 10 ** places
    magnitude = (2 * abs(scaled_change) + denominator) // (2 * denominator)
    sign = "-" if scaled_change < 0 and magnitude else ""
    if not places:
        return sign + str(magnitude)
    return f"{sign}{magnitude // 10 ** places}.{magnitude % 10 ** places:0{places}d}"


def check_line(source, sentence):
    result = {"sentence": sentence, "status": "not_verified"}
    normalized = " ".join(sentence.split())
    match = GROWTH.fullmatch(normalized) or EVERY.fullmatch(normalized) or RATIO.fullmatch(normalized)
    if match is None:
        return dict(result, reason="Unsupported whole-line claim; no partial extraction or causal check")
    claim = match.groupdict()
    before_period, after_period = claim["before"], claim["after"]
    currency = claim["currency"].upper()
    kind = "total_growth" if match.re is GROWTH else "ratio" if match.re is RATIO else "every_region_increased"
    result["interpretation"] = {
        "kind": kind,
        "metric": claim["metric"], "from_period": before_period, "to_period": after_period,
        "currency": currency, "population_scope": "exactly the source's declared regions",
    }
    try:
        population, before, after = selected_values(
            source, before_period, after_period, currency, claim["metric"], ratio=kind == "ratio")
    except ValueError as error:
        return dict(result, reason=str(error))
    result["interpretation"]["population"] = population
    if kind != "every_region_increased":
        previous, current = sum(before.values()), sum(after.values())
        if previous <= 0:
            return dict(result, reason="Percentage with a zero/negative starting denominator has no agreed definition")
        text = claim["percent"]
        places = len(text.split(".")[1]) if "." in text else 0
        calculated = ratio_percent(current if kind == "ratio" else current - previous, previous, places)
        agrees = int(text.replace(".", "")) == int(calculated.replace(".", ""))
        result["evidence"] = {"before_cents": previous, "after_cents": current,
                              "claimed_percent": text, "calculated_percent": calculated,
                              "decimal_places": places, "rounding": "nearest; ties away from zero"}
        if kind == "ratio":
            result["interpretation"]["ratio"] = {
                "numerator": source["ratio"]["numerator"], "numerator_period": after_period,
                "denominator": source["ratio"]["denominator"], "denominator_period": before_period,
                "formula": "sum(numerator at to_period) / sum(denominator at from_period) * 100",
            }
            result["evidence"].update(numerator_cents=current, denominator_cents=previous)
        reason = ("Ratio" if kind == "ratio" else "Total growth") + (
            " matches at the displayed precision" if agrees else " differs at the displayed precision")
    else:
        counterexamples = [region for region in population if after[region] <= before[region]]
        agrees = not counterexamples
        result["evidence"] = {"regions_checked": len(population),
                              "counterexamples": [{"region": region, "before_cents": before[region],
                                                   "after_cents": after[region]} for region in counterexamples]}
        reason = "Every declared region strictly increased" if agrees else "At least one declared region did not strictly increase"
    return dict(result, status="supported" if agrees else "contradicted", reason=reason)


def check_report(source, report):
    results = []
    for line, sentence in enumerate(report.splitlines(), 1):
        if not sentence.strip():
            continue
        try:
            checked = check_line(source, sentence)
        except (ValueError, RecursionError):
            checked = {"sentence": sentence, "status": "not_verified",
                       "reason": "Claim could not be checked within numeric decoding limits"}
        results.append(dict(checked, line=line))
    return {
        "execution": "completed",
        "coverage": "Every nonblank input line retained; only three whole-line sentence forms checked. No whole-report truth verdict.",
        "assumptions": "Supplied monetary metric and ratio definitions, declared population and source values are authoritative; their truth/completeness is not verified. No currency conversion or business-definition inference.",
        "freshness": "Results apply only to the recorded input bytes; rerun after inputs change.",
        "counts": {status: sum(row["status"] == status for row in results)
                   for status in ("supported", "contradicted", "not_verified")},
        "claims": results,
    }


def evaluate_source(path, report, mapping_path=None):
    """Keep unavailable sources explicit, including when only one revision is readable."""
    from csv_source import claim_records, csv_snapshot

    hashes = {"checker": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        raw = path.read_bytes()
        hashes["source"] = hashlib.sha256(raw).hexdigest()
        lineage = None
        if mapping_path is not None:
            mapping_bytes = mapping_path.read_bytes()
            hashes["mapping"] = hashlib.sha256(mapping_bytes).hexdigest()
            hashes["csv_adapter"] = hashlib.sha256(Path(__file__).with_name("csv_source.py").read_bytes()).hexdigest()
            mapping = json.loads(mapping_bytes, object_pairs_hook=unique_object)
            source, lineage = csv_snapshot(raw, mapping)
        else:
            source = json.loads(raw, object_pairs_hook=unique_object)
        result = check_report(source, report)
        result["source_status"] = "readable"
        if lineage is not None:
            result["csv_records_read"] = len(lineage)
            for claim in result["claims"]:
                claim["source_records"] = claim_records(claim, lineage)
    except (OSError, ValueError, csv.Error, RecursionError) as error:
        result = check_report(None, report)
        result["source_status"] = "unavailable"
        result["source_error"] = ("Source or mapping could not be read" if isinstance(error, OSError)
                                  else "Source or mapping could not be decoded" if isinstance(error, (UnicodeError, RecursionError))
                                  else str(error))
        for claim in result["claims"]:
            claim["reason"] = "Source unavailable: " + result["source_error"]
    result["sha256"] = hashes
    return result


def recheck(previous, current):
    """Compare the same original claims; never carry an old pass into a failed refresh."""
    results = []
    for old, new in zip(previous["claims"], current["claims"]):
        changed = [field for field in ("status", "interpretation", "evidence") if old.get(field) != new.get(field)]
        results.append({"line": new["line"], "sentence": new["sentence"],
                        "previous": old, "current": new, "changed": changed})
    return {"execution": "completed", "coverage": current["coverage"],
            "assumptions": current["assumptions"], "freshness": current["freshness"],
            "counts": current["counts"], "claims": results,
            "previous_source": {key: value for key, value in previous.items() if key not in ("claims", "counts")},
            "current_source": {key: value for key, value in current.items() if key not in ("claims", "counts")},
            "scope": "Original supplied claim lines only; changed source bytes do not establish changed meaning or narrative completeness"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Declared monetary metric snapshot JSON with signed integer cents")
    parser.add_argument("claims", type=Path, help="UTF-8 text, one complete claim per line")
    parser.add_argument("--csv-mapping", type=Path, help="Explicit CSV column/unit/population mapping JSON")
    parser.add_argument("--previous-source", type=Path, help="Recheck these same claims against an earlier source")
    parser.add_argument("--previous-csv-mapping", type=Path, help="Earlier CSV mapping; defaults to --csv-mapping")
    args = parser.parse_args()
    if args.previous_csv_mapping and (not args.previous_source or not args.csv_mapping):
        parser.error("--previous-csv-mapping requires --previous-source and --csv-mapping")
    try:
        if args.csv_mapping or args.previous_source:
            report_bytes = args.claims.read_bytes()
            report = report_bytes.decode("utf-8-sig")
            current = evaluate_source(args.source, report, args.csv_mapping)
            if args.previous_source:
                previous = evaluate_source(args.previous_source, report, args.previous_csv_mapping or args.csv_mapping)
                result = recheck(previous, current)
            else:
                result = current
            result["claims_sha256"] = hashlib.sha256(report_bytes).hexdigest()
            print(json.dumps(result, indent=2))
            return 0  # As with the original helper, inspect per-claim results.
        source_bytes, report_bytes = args.source.read_bytes(), args.claims.read_bytes()
        source = json.loads(source_bytes, object_pairs_hook=unique_object)
        result = check_report(source, report_bytes.decode("utf-8"))
        result["sha256"] = {"source": hashlib.sha256(source_bytes).hexdigest(),
                            "claims": hashlib.sha256(report_bytes).hexdigest(),
                            "checker": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    except (OSError, ValueError) as error:
        print(json.dumps({"execution": "error", "error": str(error)}))
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
