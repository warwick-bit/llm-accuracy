"""Convert an explicitly mapped CSV to the existing monetary snapshot contract."""
import csv
import io
import re


def require_text(value, label):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(label + " must be nonempty text without surrounding whitespace")
    return value


def validate_mapping(mapping):
    required = {"metric", "currency", "population", "value_unit", "columns"}
    if not isinstance(mapping, dict) or not required <= set(mapping) or set(mapping) - required - {"ratio"}:
        raise ValueError("CSV mapping needs metric, currency, population, value_unit and columns")
    require_text(mapping["metric"], "metric")
    if not isinstance(mapping["currency"], str) or not re.fullmatch(r"[A-Z]{3}", mapping["currency"]):
        raise ValueError("Mapping currency must be three uppercase ASCII letters")
    population = mapping["population"]
    if not isinstance(population, list) or not population:
        raise ValueError("Mapping needs the expected region population")
    for region in population:
        require_text(region, "region")
    if len(set(population)) != len(population):
        raise ValueError("Mapping population must be unique")
    if mapping["value_unit"] not in ("major", "cents"):
        raise ValueError("value_unit must explicitly be major or cents")
    roles = {"record_id", "period", "region", "currency", "value"}
    if "ratio" in mapping:
        ratio = mapping["ratio"]
        if not isinstance(ratio, dict) or set(ratio) != {"numerator", "denominator"}:
            raise ValueError("Ratio mapping needs numerator and denominator series names")
        for value in ratio.values():
            require_text(value, "ratio series")
        roles.add("series")
    columns = mapping["columns"]
    if not isinstance(columns, dict) or set(columns) != roles:
        raise ValueError("CSV column roles must match the documented mapping")
    for name in columns.values():
        require_text(name, "column")
    if len(set(columns.values())) != len(columns):
        raise ValueError("Each column role must use a different CSV column")


def cents(text, unit):
    text = text.strip()
    pattern = r"[+-]?[0-9]+" if unit == "cents" else r"[+-]?[0-9]+(?:\.[0-9]{1,2})?"
    if not re.fullmatch(pattern, text):
        raise ValueError("Amounts must be signed decimal numbers at the declared precision; blanks are unknown")
    if unit == "cents":
        return int(text)
    whole, _, fraction = text.lstrip("+-").partition(".")
    value = int(whole) * 100 + int(fraction.ljust(2, "0"))
    return -value if text.startswith("-") else value


def csv_snapshot(raw, mapping):
    """Read every record; refuse ambiguous input instead of dropping or deduplicating it."""
    validate_mapping(mapping)
    columns = mapping["columns"]
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    header = next(reader, None)
    if not header or any(not cell or cell.strip() != cell for cell in header) or len(set(header)) != len(header):
        raise ValueError("CSV needs nonempty unique header names")
    if not set(columns.values()) <= set(header):
        raise ValueError("CSV is missing mapped columns")
    source = {key: mapping[key] for key in ("metric", "currency", "population")}
    ratio = mapping.get("ratio")
    source["series_cents" if ratio else "values_cents"] = {}
    if ratio:
        source["ratio"] = ratio
    seen, lineage = set(), []
    previous_line = reader.line_num
    for record, cells in enumerate(reader, 1):
        start, previous_line = previous_line + 1, reader.line_num
        if len(cells) != len(header):
            raise ValueError("CSV record has missing or extra fields at record " + str(record))
        row = dict(zip(header, cells))
        values = {role: row[name] for role, name in columns.items()}
        record_id = require_text(values["record_id"], "record_id")
        if record_id in seen:
            raise ValueError("Duplicate record_id; resolve revisions or duplicates before checking")
        seen.add(record_id)
        period, region = values["period"], values["region"]
        if not re.fullmatch(r"[1-9][0-9]{3}-(?:0[1-9]|1[0-2])", period):
            raise ValueError("CSV period must be YYYY-MM")
        if region not in mapping["population"]:
            raise ValueError("CSV includes a region outside the declared population")
        if values["currency"] != mapping["currency"]:
            raise ValueError("CSV currency differs from mapping; no mixed currencies or conversion")
        amount = cents(values["value"], mapping["value_unit"])
        series = require_text(values["series"], "series") if ratio else None
        if ratio and series not in ratio.values():
            raise ValueError("CSV includes an undeclared ratio series")
        periods = source["series_cents"].setdefault(series, {}) if ratio else source["values_cents"]
        regions = periods.setdefault(period, {})
        regions[region] = regions.get(region, 0) + amount
        lineage.append({"record": record, "record_id": record_id, "lines": [start, reader.line_num],
                        "period": period, "region": region, "series": series, "value_cents": amount})
    return source, lineage


def claim_records(claim, lineage):
    """Attach only source records selected by this claim's explicit interpretation."""
    interpretation = claim.get("interpretation", {})
    before, after = interpretation.get("from_period"), interpretation.get("to_period")
    ratio = interpretation.get("ratio")
    if interpretation.get("kind") == "ratio" and not ratio:
        return []  # An invalid ratio has no established series selection.
    return [row for row in lineage if (
        (row["period"], row["series"]) in ((before, ratio["denominator"]), (after, ratio["numerator"]))
        if ratio else row["period"] in (before, after) and row["series"] is None
    )]
