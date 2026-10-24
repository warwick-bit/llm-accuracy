#!/usr/bin/env python3
"""Local experiment: check two whole-line revenue claims against a supplied snapshot.

No model, automatic claim extraction, source authentication or plugin integration.
Exit 0 means execution completed; inspect each claim's status, not the exit code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


PERIOD = r"[1-9][0-9]{3}-(?:0[1-9]|1[0-2])"
WINDOW = rf" from (?P<before>{PERIOD}) to (?P<after>{PERIOD}) in (?P<currency>[A-Z]{{3}})\.?"
GROWTH = re.compile(r"Total revenue growth was (?P<percent>[+-]?[0-9]+(?:\.[0-9]{1,2})?)%" + WINDOW, re.I)
EVERY = re.compile(r"Revenue increased for every region" + WINDOW, re.I)


def unique_object(pairs):
    """Do not let JSON silently replace an earlier region, period or definition."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; source is ambiguous")
        result[key] = value
    return result


def selected_values(source, before, after, currency):
    if not isinstance(source, dict) or source.get("metric") != "revenue":
        raise ValueError("Source must explicitly define metric as revenue")
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
    if not isinstance(periods, dict):
        raise ValueError("Missing revenue values_cents by period")
    values = []
    for period in (before, after):
        rows = periods.get(period)
        if not isinstance(rows, dict) or set(rows) != set(population):
            raise ValueError("Missing or extra region values for " + period)
        if any(type(value) is not int for value in rows.values()):
            raise ValueError("Revenue values must be signed integer cents")
        values.append(rows)
    return population, values[0], values[1]


def growth_percent(before, after, places):
    """Exact integer-ratio rounding, ties away from zero; before must be positive."""
    scaled_change = (after - before) * 100 * 10 ** places
    magnitude = (2 * abs(scaled_change) + before) // (2 * before)
    sign = "-" if scaled_change < 0 and magnitude else ""
    if not places:
        return sign + str(magnitude)
    return f"{sign}{magnitude // 10 ** places}.{magnitude % 10 ** places:0{places}d}"


def check_line(source, sentence):
    result = {"sentence": sentence, "status": "not_verified"}
    normalized = " ".join(sentence.split())
    match = GROWTH.fullmatch(normalized) or EVERY.fullmatch(normalized)
    if match is None:
        return dict(result, reason="Unsupported whole-line claim; no partial extraction or causal check")
    claim = match.groupdict()
    before_period, after_period = claim["before"], claim["after"]
    currency = claim["currency"].upper()
    result["interpretation"] = {
        "kind": "total_growth" if "percent" in claim else "every_region_increased",
        "metric": "revenue", "from_period": before_period, "to_period": after_period,
        "currency": currency, "population_scope": "exactly the source's declared regions",
    }
    try:
        population, before, after = selected_values(source, before_period, after_period, currency)
    except ValueError as error:
        return dict(result, reason=str(error))
    result["interpretation"]["population"] = population
    if "percent" in claim:
        previous, current = sum(before.values()), sum(after.values())
        if previous <= 0:
            return dict(result, reason="Growth for a zero/negative starting total has no agreed definition")
        text = claim["percent"]
        places = len(text.split(".")[1]) if "." in text else 0
        calculated = growth_percent(previous, current, places)
        agrees = int(text.replace(".", "")) == int(calculated.replace(".", ""))
        result["evidence"] = {"before_cents": previous, "after_cents": current,
                              "claimed_percent": text, "calculated_percent": calculated,
                              "decimal_places": places, "rounding": "nearest; ties away from zero"}
        reason = "Total growth matches at the displayed precision" if agrees else "Total growth differs at the displayed precision"
    else:
        counterexamples = [region for region in population if after[region] <= before[region]]
        agrees = not counterexamples
        result["evidence"] = {"regions_checked": len(population),
                              "counterexamples": [{"region": region, "before_cents": before[region],
                                                   "after_cents": after[region]} for region in counterexamples]}
        reason = "Every declared region strictly increased" if agrees else "At least one declared region did not strictly increase"
    return dict(result, status="supported" if agrees else "contradicted", reason=reason)


def check_report(source, report):
    results = [dict(check_line(source, sentence), line=line)
               for line, sentence in enumerate(report.splitlines(), 1) if sentence.strip()]
    return {
        "execution": "completed",
        "coverage": "Every nonblank input line retained; only two whole-line sentence forms checked. No whole-report truth verdict.",
        "assumptions": "Supplied revenue definition, declared population and source values are authoritative; their truth/completeness is not verified.",
        "freshness": "Results apply only to the recorded input bytes; rerun after inputs change.",
        "counts": {status: sum(row["status"] == status for row in results)
                   for status in ("supported", "contradicted", "not_verified")},
        "claims": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Revenue snapshot JSON with signed integer cents")
    parser.add_argument("claims", type=Path, help="UTF-8 text, one complete claim per line")
    args = parser.parse_args()
    try:
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
