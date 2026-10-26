"""Exercise final-report coverage and evidence freshness through the delivered CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/scripts/check_report_inventory.py"
CLAIM = "Total revenue growth was 12% from 2026-08 to 2026-09 in AUD."
POLICY = "The minimum balance is AUD 150,000."


def run(report, inventory, code=0):
    process = subprocess.run([sys.executable, "-B", str(SCRIPT), str(report), str(inventory)],
                             cwd=report.parent.parent, capture_output=True, text=True, timeout=30,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert process.returncode == code, (process.stdout, process.stderr)
    assert process.stderr == ""
    return json.loads(process.stdout)


@pytest.fixture
def inputs(tmp_path):
    report, inventory, source, policy = [tmp_path / name for name in
                                         ("final.md", "inventory.json", "numbers.json", "policy.txt")]
    source.write_text(json.dumps({"metric": "revenue", "currency": "AUD", "population": ["North"],
                                 "values_cents": {"2026-08": {"North": 10000}, "2026-09": {"North": 11200}}}),
                      encoding="utf-8")
    policy.write_bytes(b"The current minimum balance is AUD 150,000.\n")
    report.write_text(CLAIM + "\n" + POLICY + "\nPricing caused the increase.\n", encoding="utf-8")
    items = [{"id": "growth", "text": CLAIM, "numerical": {"source": source.name}},
             {"id": "minimum", "text": POLICY, "review": {"source": policy.name,
              "sha256": hashlib.sha256(policy.read_bytes()).hexdigest(), "assessment": "supported",
              "reason": "Explicit threshold in the supplied policy; no broader scope inferred"}}]
    inventory.write_text(json.dumps({"assertions": items}), encoding="utf-8")
    return report, inventory, source, policy


def test_side_claims_are_visible_and_manual_review_is_not_machine_truth(inputs):
    report, inventory, source, policy = inputs
    original = {path: path.read_bytes() for path in inputs}
    result = run(report, inventory)
    assert result["unlisted_lines"] == [{"line": 3, "text": "Pricing caused the increase.",
                                         "assertion_id": None, "status": "not_verified"}]
    growth, minimum = result["assertions"]
    assert growth["status"] == "supported"
    assert growth["numerical"]["sha256"]["source"] == hashlib.sha256(original[source]).hexdigest()
    assert minimum["review"]["source_binding"] == "current"
    assert minimum["review"]["declared_assessment"] == "supported"
    assert minimum["status"] == "not_verified"
    assert result["sha256"]["report"] == hashlib.sha256(original[report]).hexdigest()
    assert result["coverage"]["semantic_completeness"] == "not_verified"
    assert all(path.read_bytes() == raw for path, raw in original.items())


def test_changed_sources_recompute_numbers_and_invalidate_policy_review(inputs):
    report, inventory, source, policy = inputs
    data = json.loads(source.read_text())
    data["values_cents"]["2026-09"]["North"] = 10900
    source.write_text(json.dumps(data), encoding="utf-8")
    policy.write_bytes(b"The current minimum balance is AUD 160,000.\n")
    growth, minimum = run(report, inventory)["assertions"]
    assert growth["status"] == "contradicted"
    assert minimum["review"]["source_binding"] == "stale"
    assert minimum["review"]["declared_assessment"] == "supported"
    assert minimum["status"] == "not_verified"


def test_final_shortening_does_not_reuse_old_assertion_checks(inputs):
    report, inventory, _, _ = inputs
    report.write_text("Revenue grew 12%.\nThe minimum balance is AUD 160,000.\n", encoding="utf-8")
    result = run(report, inventory)
    assert result["missing_assertions"] == ["growth", "minimum"]
    assert result["coverage"]["unlisted_lines"] == 2
    assert all(item["status"] == "not_verified" for item in result["assertions"])
    assert all("numerical" not in item and "review" not in item for item in result["assertions"])


def test_valid_formatting_order_and_repeated_occurrences_are_retained(inputs):
    report, inventory, _, _ = inputs
    report.write_bytes(("\ufeff  " + POLICY + "  \r\n\r\n" + CLAIM + "\r\n" + CLAIM + "\r\n").encode("utf-8"))
    result = run(report, inventory)
    assert result["missing_assertions"] == []
    assert result["unlisted_lines"] == []
    assert result["assertions"][0]["report_lines"] == [3, 4]
    assert result["assertions"][1]["report_lines"] == [1]
    assert result["coverage"] == {"nonblank_lines": 3, "listed_lines": 3, "unlisted_lines": 0,
                                    "semantic_completeness": "not_verified"}


@pytest.mark.parametrize("missing", ["numbers", "policy"])
def test_unavailable_source_preserves_independently_checkable_results(inputs, missing):
    report, inventory, source, policy = inputs
    (source if missing == "numbers" else policy).unlink()
    growth, minimum = run(report, inventory)["assertions"]
    assert growth["status"] == ("not_verified" if missing == "numbers" else "supported")
    assert minimum["review"]["source_binding"] == ("current" if missing == "numbers" else "unavailable")


def test_explicitly_unchecked_line_and_empty_inventory_do_not_hide_content(inputs):
    report, inventory, _, _ = inputs
    inventory.write_text(json.dumps({"assertions": [{"id": "policy", "text": POLICY,
                                                    "note": "Evidence not yet supplied"}]}), encoding="utf-8")
    result = run(report, inventory)
    assert result["assertions"][0]["status"] == "not_verified"
    assert result["coverage"]["unlisted_lines"] == 2
    inventory.write_text('{"assertions": []}', encoding="utf-8")
    assert run(report, inventory)["coverage"]["unlisted_lines"] == 3
    report.write_bytes(b"\n  \n")
    assert run(report, inventory)["coverage"] == {"nonblank_lines": 0, "listed_lines": 0, "unlisted_lines": 0,
                                                 "semantic_completeness": "not_verified"}


def test_inventory_uses_explicit_csv_mapping_and_preserves_its_source_binding(inputs):
    report, inventory, source, _ = inputs
    source = source.with_suffix(".csv")
    source.write_bytes(b"id,period,region,currency,value\na,2026-08,North,AUD,100\nb,2026-09,North,AUD,112\n")
    mapping = source.with_name("mapping.json")
    mapping.write_text(json.dumps({"metric": "revenue", "currency": "AUD", "population": ["North"],
                                  "value_unit": "major", "columns": {"record_id": "id", "period": "period",
                                  "region": "region", "currency": "currency", "value": "value"}}), encoding="utf-8")
    data = {"assertions": [{"id": "growth", "text": CLAIM,
                           "numerical": {"source": source.name, "csv_mapping": mapping.name}}]}
    inventory.write_text(json.dumps(data), encoding="utf-8")
    item = run(report, inventory)["assertions"][0]
    assert item["status"] == "supported"
    assert item["numerical"]["sha256"]["mapping"] == hashlib.sha256(mapping.read_bytes()).hexdigest()
    assert [row["record_id"] for row in item["numerical"]["claims"][0]["source_records"]] == ["a", "b"]


@pytest.mark.parametrize("bad", ["duplicate_key", "duplicate_id", "duplicate_text", "both", "hash", "multiline", "shape"])
def test_ambiguous_or_malformed_inventory_returns_structured_error(inputs, bad):
    report, inventory, _, _ = inputs
    data = json.loads(inventory.read_text())
    if bad == "duplicate_id":
        data["assertions"][1]["id"] = "growth"
    elif bad == "duplicate_text":
        data["assertions"][1]["text"] = "  " + CLAIM
    elif bad == "both":
        data["assertions"][1]["numerical"] = {"source": "numbers.json"}
    elif bad == "hash":
        data["assertions"][1]["review"]["sha256"] = "missing"
    elif bad == "multiline":
        data["assertions"][0]["text"] += "\n" + POLICY
    elif bad == "shape":
        data["assertions"] = "wrong"
    inventory.write_text('{"assertions": [], "assertions": []}' if bad == "duplicate_key" else json.dumps(data),
                         encoding="utf-8")
    assert run(report, inventory, code=2)["execution"] == "error"
