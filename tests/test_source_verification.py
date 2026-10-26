"""Consumer regressions for explicit source mapping and changed-evidence checks."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/llm-accuracy/scripts/check_numerical_claims.py"
GROWTH = "Total revenue growth was 12% from 2026-08 to 2026-09 in AUD."
EVERY = "Revenue increased for every region from 2026-08 to 2026-09 in AUD."
HEADER = ["id", "month", "area", "ccy", "amount"]
ROWS = [["n0", "2026-08", "North", "AUD", "1000.00"],
        ["s0", "2026-08", "South", "AUD", "2000.00"],
        ["n1", "2026-09", "North", "AUD", "1200.00"],
        ["s1", "2026-09", "South", "AUD", "2160.00"]]


def mapping():
    return {"metric": "revenue", "currency": "AUD", "population": ["North", "South"],
            "value_unit": "major", "columns": dict(zip(
                ("record_id", "period", "region", "currency", "value"), HEADER))}


def write_csv(path, rows, header=HEADER):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    path.write_bytes(stream.getvalue().encode("utf-8"))


def run_cli(source, claims, *options):
    process = subprocess.run([sys.executable, "-B", str(SCRIPT), str(source), str(claims), *map(str, options)],
                             capture_output=True, text=True, timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert process.returncode == 0, (process.stdout, process.stderr)
    assert process.stderr == ""
    return json.loads(process.stdout)


@pytest.fixture
def inputs(tmp_path):
    source, spec, claims = (tmp_path / name for name in ("source.csv", "mapping.json", "claims.txt"))
    write_csv(source, ROWS)
    spec.write_text(json.dumps(mapping()), encoding="utf-8")
    claims.write_text(GROWTH + "\n" + EVERY + "\nPricing caused the increase.\n", encoding="utf-8")
    return source, spec, claims


def test_csv_preserves_claims_source_bytes_and_record_lineage(inputs):
    source, spec, claims = inputs
    original = {path: path.read_bytes() for path in inputs}
    result = run_cli(source, claims, "--csv-mapping", spec)
    assert result["counts"] == {"supported": 2, "contradicted": 0, "not_verified": 1}
    assert result["csv_records_read"] == 4
    claim = result["claims"][0]
    assert claim["evidence"]["before_cents"] == 300000
    assert claim["evidence"]["after_cents"] == 336000
    assert [row["record_id"] for row in claim["source_records"]] == ["n0", "s0", "n1", "s1"]
    assert [row["lines"] for row in claim["source_records"]] == [[2, 2], [3, 3], [4, 4], [5, 5]]
    assert result["claims"][2]["source_records"] == []
    assert result["sha256"]["source"] == hashlib.sha256(original[source]).hexdigest()
    assert result["sha256"]["mapping"] == hashlib.sha256(original[spec]).hexdigest()
    assert all(path.read_bytes() == raw for path, raw in original.items())


def test_reordered_records_and_split_transactions_are_valid_alternatives(inputs, tmp_path):
    source, spec, claims = inputs
    previous = tmp_path / "previous.csv"
    previous.write_bytes(source.read_bytes())
    # Two distinct transactions for one cell are added, not mistaken for duplicate records.
    rows = ROWS[:3] + [["s1a", "2026-09", "South", "AUD", "1000"],
                      ["s1b", "2026-09", "South", "AUD", "1160"]]
    write_csv(source, list(reversed(rows)))
    result = run_cli(source, claims, "--csv-mapping", spec, "--previous-source", previous)
    assert result["counts"]["supported"] == 2
    assert all(claim["changed"] == [] for claim in result["claims"])
    assert result["previous_source"]["sha256"]["source"] != result["current_source"]["sha256"]["source"]


@pytest.mark.parametrize("failure", ["duplicate_id", "mixed_currency", "unknown_region", "blank_amount",
                                     "precision", "extra_field", "duplicate_header", "bad_mapping", "empty"])
def test_csv_cannot_turn_unknown_or_ambiguous_inputs_into_a_pass(inputs, failure):
    source, spec, claims = inputs
    rows = [row[:] for row in ROWS]
    header = HEADER[:]
    if failure == "duplicate_id":
        rows.append(rows[0][:])
    elif failure == "mixed_currency":
        rows[1][3] = "USD"
    elif failure == "unknown_region":
        rows[1][2] = "West"
    elif failure == "blank_amount":
        rows[1][4] = ""
    elif failure == "precision":
        rows[1][4] = "2000.001"
    elif failure == "extra_field":
        rows[1].append("unexpected")
    elif failure == "duplicate_header":
        header[1] = header[0]
    elif failure == "bad_mapping":
        bad = mapping()
        bad["value_unit"] = "guess"
        spec.write_text(json.dumps(bad), encoding="utf-8")
    else:
        rows = []
    write_csv(source, rows, header)
    result = run_cli(source, claims, "--csv-mapping", spec)
    assert result["counts"] == {"supported": 0, "contradicted": 0, "not_verified": 3}
    assert len(result["claims"]) == 3
    assert all("evidence" not in claim for claim in result["claims"])


def test_missing_region_does_not_become_zero_and_other_periods_remain_checkable(inputs):
    source, spec, claims = inputs
    write_csv(source, ROWS + [["n2", "2026-10", "North", "AUD", "1300"]])
    claims.write_text(GROWTH + "\n" + GROWTH.replace("2026-08", "2026-09").replace("2026-09 in", "2026-10 in"), encoding="utf-8")
    result = run_cli(source, claims, "--csv-mapping", spec)
    assert [claim["status"] for claim in result["claims"]] == ["supported", "not_verified"]
    assert "Missing or extra region" in result["claims"][1]["reason"]


def test_changed_source_rechecks_same_claims_and_failed_refresh_keeps_history(inputs, tmp_path):
    source, spec, claims = inputs
    previous = tmp_path / "previous.csv"
    previous.write_bytes(source.read_bytes())
    rows = [row[:] for row in ROWS]
    rows[-1][-1] = "2070"  # (1200 + 2070) / 3000 - 1 = 9%.
    write_csv(source, rows)
    result = run_cli(source, claims, "--csv-mapping", spec, "--previous-source", previous)
    claim = result["claims"][0]
    assert claim["previous"]["status"] == "supported"
    assert claim["current"]["status"] == "contradicted"
    assert claim["current"]["evidence"]["calculated_percent"] == "9"
    assert claim["changed"] == ["status", "evidence"]
    assert result["claims"][1]["current"]["status"] == "supported"
    absent = source.with_name("unavailable.csv")
    failed = run_cli(absent, claims, "--csv-mapping", spec, "--previous-source", previous)
    assert failed["current_source"]["source_status"] == "unavailable"
    assert failed["claims"][0]["current"]["status"] == "not_verified"
    assert failed["claims"][0]["previous"]["status"] == "supported"
    assert source.read_bytes() != previous.read_bytes()  # Neither file was rewritten by recheck.


def test_json_recheck_and_definition_changes_are_explicit(inputs, tmp_path):
    _, _, claims = inputs
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    source = {"metric": "revenue", "currency": "AUD", "population": ["North"],
              "values_cents": {"2026-08": {"North": 10000}, "2026-09": {"North": 11200}}}
    old.write_text(json.dumps(source), encoding="utf-8")
    source["currency"] = "USD"
    new.write_text(json.dumps(source), encoding="utf-8")
    result = run_cli(new, claims, "--previous-source", old)
    assert result["claims"][0]["previous"]["status"] == "supported"
    assert result["claims"][0]["current"]["status"] == "not_verified"
    assert "currency" in result["claims"][0]["current"]["reason"]
    old.unlink()
    result = run_cli(new, claims, "--previous-source", old)
    assert result["previous_source"]["source_status"] == "unavailable"
    assert result["current_source"]["source_status"] == "readable"


def test_previous_csv_mapping_is_used_without_changing_current_definition(inputs, tmp_path):
    source, spec, claims = inputs
    old, old_spec = tmp_path / "old.csv", tmp_path / "old-mapping.json"
    config = mapping()
    config["value_unit"] = "cents"
    old_spec.write_text(json.dumps(config), encoding="utf-8")
    write_csv(old, [row[:4] + [row[4].replace(".", "")] for row in ROWS])
    result = run_cli(source, claims, "--csv-mapping", spec, "--previous-source", old,
                     "--previous-csv-mapping", old_spec)
    assert result["claims"][0]["changed"] == []
    assert result["claims"][0]["previous"]["status"] == "supported"
    assert result["previous_source"]["sha256"]["mapping"] != result["current_source"]["sha256"]["mapping"]


def test_cents_and_signed_major_values_are_exact(inputs):
    source, spec, claims = inputs
    config = mapping()
    config["value_unit"] = "cents"
    spec.write_text(json.dumps(config), encoding="utf-8")
    rows = [row[:4] + [str(int(row[4].replace(".", "")))] for row in ROWS]
    rows += [["credit", "2026-09", "South", "AUD", "-1"],
             ["debit", "2026-09", "South", "AUD", "+1"]]
    write_csv(source, rows)
    assert run_cli(source, claims, "--csv-mapping", spec)["claims"][0]["evidence"]["after_cents"] == 336000
    spec.write_text(json.dumps(mapping()), encoding="utf-8")
    write_csv(source, ROWS + [["credit", "2026-09", "South", "AUD", "-0.01"]])
    assert run_cli(source, claims, "--csv-mapping", spec)["claims"][0]["evidence"]["after_cents"] == 335999


def test_ratio_csv_uses_named_series_and_multiline_record_locations(inputs):
    source, spec, claims = inputs
    config = mapping()
    config.update(metric="Gross revenue retention", ratio={"numerator": "retained", "denominator": "starting"})
    config["columns"]["series"] = "series"
    spec.write_text(json.dumps(config), encoding="utf-8")
    rows = [row[:] + ["starting" if row[1] == "2026-08" else "retained"] for row in ROWS]
    rows[0][0] = "first\nrecord"
    write_csv(source, rows, HEADER + ["series"])
    claims.write_text("Gross revenue retention was 112% from 2026-08 to 2026-09 in AUD.", encoding="utf-8")
    result = run_cli(source, claims, "--csv-mapping", spec)["claims"][0]
    assert result["status"] == "supported"
    assert result["evidence"]["numerator_cents"] == 336000
    assert result["source_records"][0]["lines"] == [2, 3]
    assert result["source_records"][1]["lines"] == [4, 4]


def test_one_uncheckable_numeric_claim_does_not_discard_other_results(inputs):
    source, spec, claims = inputs
    claims.write_text(GROWTH.replace("12%", "1" * 5000 + "%") + "\n" + GROWTH, encoding="utf-8")
    result = run_cli(source, claims, "--csv-mapping", spec)
    assert result["claims"][0]["status"] in ("not_verified", "contradicted")
    assert result["claims"][1]["status"] == "supported"
