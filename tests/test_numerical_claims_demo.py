"""Five bounded consumer checks; expected figures are hand-calculated fixtures."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/llm-accuracy/scripts/check_numerical_claims.py"
FIXTURES = ROOT / "tests/fixtures/numerical-claims"
spec = importlib.util.spec_from_file_location("numerical_claims_demo", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
SOURCE = json.loads((FIXTURES / "source.json").read_bytes())
GROWTH = "Total revenue growth was 12% from 2026-08 to 2026-09 in AUD."
EVERY = "Revenue increased for every region from 2026-08 to 2026-09 in AUD."


def cli(source, claims, expected_exit=0):
    process = subprocess.run([sys.executable, "-B", str(SCRIPT), str(source), str(claims)],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == expected_exit, (process.stdout, process.stderr)
    return json.loads(process.stdout)


def test_cli_preserves_all_claims_and_exact_input_bindings():
    source_path, claims_path = FIXTURES / "source.json", FIXTURES / "claims.txt"
    source_bytes, claims_bytes = source_path.read_bytes(), claims_path.read_bytes()
    result = cli(source_path, claims_path)
    assert result["counts"] == {"supported": 2, "contradicted": 1, "not_verified": 2}
    assert [r["sentence"] for r in result["claims"]] == claims_bytes.decode().splitlines()
    assert [r["line"] for r in result["claims"]] == [1, 2, 3, 4, 5]
    assert result["claims"][0]["evidence"]["before_cents"] == 300000
    assert result["claims"][0]["evidence"]["after_cents"] == 336000
    assert result["claims"][1]["evidence"]["calculated_percent"] == "12"
    assert "partial extraction" in result["claims"][4]["reason"]
    assert result["sha256"] == {"source": hashlib.sha256(source_bytes).hexdigest(),
                                "claims": hashlib.sha256(claims_bytes).hexdigest(),
                                "checker": hashlib.sha256(SCRIPT.read_bytes()).hexdigest()}
    assert source_path.read_bytes() == source_bytes and claims_path.read_bytes() == claims_bytes
    legacy = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/numerical_claims_demo.py"),
         str(source_path), str(claims_path)], capture_output=True, text=True, timeout=30)
    assert legacy.returncode == 0 and json.loads(legacy.stdout) == result


def test_changed_source_contradicts_the_same_old_sentence(tmp_path):
    source_path, claims_path = tmp_path / "source.json", tmp_path / "claims.txt"
    source = copy.deepcopy(SOURCE)
    source_path.write_bytes(json.dumps(source).encode())
    claims_path.write_bytes(GROWTH.encode())
    original = cli(source_path, claims_path)
    assert original["claims"][0]["status"] == "supported"
    source["values_cents"]["2026-09"]["South"] = 207000  # 3270 / 3000 => 9%
    source_path.write_bytes(json.dumps(source).encode())
    stale = cli(source_path, claims_path)
    assert stale["claims"][0]["status"] == "contradicted"
    assert stale["claims"][0]["evidence"]["calculated_percent"] == "9"
    assert stale["sha256"]["claims"] == original["sha256"]["claims"]
    assert stale["sha256"]["source"] != original["sha256"]["source"]
    claims_path.write_bytes(GROWTH.replace("12%", "9%").encode())
    assert cli(source_path, claims_path)["claims"][0]["status"] == "supported"


def test_aggregate_growth_does_not_prove_every_region_increased():
    source = copy.deepcopy(SOURCE)
    source["values_cents"]["2026-09"] = {"North": 140000, "South": 196000}
    assert demo.check_line(source, GROWTH)["status"] == "supported"  # still 12%
    result = demo.check_line(source, EVERY)
    assert result["status"] == "contradicted"
    assert result["evidence"]["counterexamples"] == [
        {"region": "South", "before_cents": 200000, "after_cents": 196000}]
    source["values_cents"]["2026-09"]["South"] = 200000  # equal is not increased
    assert demo.check_line(source, EVERY)["status"] == "contradicted"
    del source["values_cents"]["2026-09"]["South"]
    assert demo.check_line(source, EVERY)["status"] == "not_verified"
    for population in ([], ["North", "North"]):
        source["population"] = population
        assert demo.check_line(source, EVERY)["status"] == "not_verified"


def test_legitimate_variants_rounding_and_scope_boundaries():
    source = copy.deepcopy(SOURCE)
    source["population"].reverse()
    source["values_cents"] = dict(reversed(list(source["values_cents"].items())))
    variant = "  TOTAL   revenue growth was +12.00% from 2026-08 to 2026-09 in aud  "
    result = demo.check_report(source, EVERY + "\n\n" + variant)
    assert [r["status"] for r in result["claims"]] == ["supported", "supported"]
    assert result["claims"][1]["sentence"] == variant
    assert result["claims"][1]["line"] == 3
    for text in (GROWTH.replace("AUD", "USD"), GROWTH.replace("2026-08", "2026-07"),
                 GROWTH.replace("2026-08", "2026-09")):
        assert demo.check_line(source, text)["status"] == "not_verified"
    source["population"] = ["North"]
    # 12.49%, positive/negative half ties, a credit current value and zero growth.
    for before, after, percent in ((10000, 11249, "12"), (10000, 11249, "12.49"),
                                   (800, 900, "13"), (800, 700, "-13"),
                                   (100, -100, "-200"), (100, 100, "0.00")):
        source["values_cents"] = {"2026-08": {"North": before}, "2026-09": {"North": after}}
        assert demo.check_line(source, GROWTH.replace("12%", percent + "%"))["status"] == "supported"
    source["values_cents"] = {"2026-08": {"North": 800}, "2026-09": {"North": 900}}
    assert demo.check_line(source, GROWTH)["status"] == "contradicted"  # 12.5 rounds to 13
    for before in (0, -100):
        source["values_cents"]["2026-08"]["North"] = before
        assert demo.check_line(source, GROWTH)["status"] == "not_verified"


def test_ambiguous_source_is_execution_error_and_empty_report_has_no_verdict(tmp_path):
    source_path = tmp_path / "duplicate.json"
    source_path.write_bytes(b'{"metric":"revenue","metric":"profit"}')
    result = cli(source_path, FIXTURES / "claims.txt", expected_exit=2)
    assert result["execution"] == "error" and "Duplicate JSON key" in result["error"]
    assert "claims" not in result
    empty = demo.check_report(SOURCE, "\n \n")
    assert empty["claims"] == [] and empty["counts"] == {
        "supported": 0, "contradicted": 0, "not_verified": 0}
    source = copy.deepcopy(SOURCE)
    source["values_cents"]["2026-08"]["North"] = True
    assert demo.check_line(source, GROWTH)["status"] == "not_verified"
