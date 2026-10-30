"""Exercise the shipped read-only CLI, including quoted history and stale bytes."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/llm-accuracy/scripts"


def invoke(tmp_path, text, *args):
    report = tmp_path / "report.md"
    report.write_text(text, encoding="utf-8")
    original = report.read_bytes()
    process = subprocess.run([sys.executable, "-B", str(SCRIPTS / "check_saved_output.py"),
                              str(report), *args], capture_output=True, text=True, timeout=20,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert not process.stderr
    result = json.loads(process.stdout)
    assert result["whole_report_status"] == "unverified"
    assert report.read_bytes() == original
    return process.returncode, result


@pytest.mark.parametrize("text,status,exit_code", [
    ("Cost formula: 930 - 775 = 155 GBP.", "bounded_checks_pass", 0),
    ("Cost formula: (930 - 775) / 775 = 0.2.", "bounded_checks_pass", 0),
    ("Cost formula: (930 - 775) / 775 = 155, +20%.", "fail", 1),
    ("Cost formula: 0.3 - 0.1 = 0.2.", "bounded_checks_pass", 0),
    ("Cost formula: 0.10000000000000000001 = 0.1.", "fail", 1),
    ("Cost formula: 0.10000000000000000001 - 0.1 = 0.00000000000000000001.", "bounded_checks_pass", 0),
    ("Cost formula: (80 − 100) / 100 = −0.2.", "bounded_checks_pass", 0),
    ("Cost formula: 2 ** 3 = 8.", "unavailable", 2),
    ("Cost formula: 1 / 0 = 0.", "unavailable", 2),
    ("Cost formula: total - cost = remainder.", "unavailable", 2),
    ("Cost formula: 1 / 5 = 1 / 5.", "unavailable", 2),
    ("Cost formula: 1 / 5 = 0.2e99.", "unavailable", 2),
    ("Cost formula: 1000 + 250 = 1,250.", "unavailable", 2),
    ("Cost formula: 1 / 5 = 0.2 = 20%.", "unavailable", 2),
    ("Cost formula: (930 - 775) / 775 = 21%.", "not_applicable", 0),
    ("Change: +155 GBP (+20%).", "not_applicable", 0),
    ("> Cost formula: 1 + 1 = 3.", "not_applicable", 0),
    ("```text\nCost formula: 1 + 1 = 3.\n```", "not_applicable", 0),
    ("~~~text\nCost formula: 1 + 1 = 3.\n~~~\nCost formula: 1 + 1 = 2.", "bounded_checks_pass", 0),
    ("```text\nCost formula: 1 + 1 = 3.\n```\nCost formula: 1 + 1 = 3.", "fail", 1),
])
def test_real_cli_formula_boundaries(tmp_path, text, status, exit_code):
    code, result = invoke(tmp_path, text)
    assert (code, result["status"]) == (exit_code, status)


def test_digest_generic_claim_correct_wrong_and_unavailable(tmp_path):
    source = tmp_path / "earlier.md"
    source.write_bytes(b"Original historical evidence\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    generic = "I computed SHA-256 checksums for the files.\n"
    code, result = invoke(tmp_path, generic + "SHA-256 v1: " + digest, "--source", "v1=" + str(source))
    assert code == 0 and result["digest_checks"]["status"] == "pass"
    assert result["digest_checks"]["nonnumeric_sha256_lines_for_narrative_review"] == [1]
    code, result = invoke(tmp_path, "SHA-256 v1: " + "0" * 64, "--source", "v1=" + str(source))
    assert code == 1 and result["digest_checks"]["status"] == "fail"
    for text in ("SHA-256: " + digest, "SHA-256 v2: " + digest, "SHA-256 v1: deadbeef"):
        code, result = invoke(tmp_path, text, "--source", "v1=" + str(source))
        assert code == 2 and result["digest_checks"]["status"] == "unavailable"


def test_delivery_checked_and_inputs_bound(tmp_path):
    delivery = tmp_path / "delivery.txt"
    delivery.write_text("Cost formula: 2 + 2 = 5.", encoding="utf-8")
    code, result = invoke(tmp_path, "Current data is supplied separately.", "--delivery", str(delivery))
    assert code == 1 and result["formula_checks"]["delivery"]["status"] == "fail"
    assert result["input_sha256"][str(delivery.resolve())] == hashlib.sha256(delivery.read_bytes()).hexdigest()


def test_wrong_binding_missing_file_and_duplicate_version_unavailable(tmp_path):
    for args in (("--expected-sha256", "0" * 64),
                 ("--source", "v1=" + str(tmp_path / "missing.md")),
                 ("--source", "v3=" + str(tmp_path / "report.md"))):
        code, result = invoke(tmp_path, "Cost formula: 1 + 1 = 2.", *args)
        assert code == 2 and result["status"] == "unavailable"


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_precision_and_quotation_regressions_detect_restored_defects(tmp_path):
    source = (SCRIPTS / "saved_output_formulas.py").read_text(encoding="utf-8")
    current = load_module(SCRIPTS / "saved_output_formulas.py", "current_formulas")
    literal = "Fraction(ast.get_source_segment(text,node))"
    assert source.count(literal) == 1
    old_path = tmp_path / "lossy.py"
    old_path.write_text(source.replace(literal, "Fraction(str(node.value))"), encoding="utf-8")
    old = load_module(old_path, "lossy_formulas")
    text = "Cost formula: 0.10000000000000000001 = 0.1."
    assert current.check(text)["status"] == "fail" and old.check(text)["status"] == "pass"
    boundary = "if fence is not None or line.lstrip().startswith('>'):continue"
    assert source.count(boundary) == 1
    old_path = tmp_path / "unquoted.py"
    old_path.write_text(source.replace(boundary, "if False:continue"), encoding="utf-8")
    old = load_module(old_path, "unquoted_formulas")
    text = "```text\nCost formula: 1 + 1 = 3.\n```"
    assert current.check(text)["status"] == "not_applicable" and old.check(text)["status"] == "fail"


def test_independently_mounted_saved_output_skill(tmp_path):
    """A host mounting only the skill can execute its shipped helper."""
    import shutil
    original = ROOT / "plugins/llm-accuracy/skills/saved-output-audit"
    mounted = tmp_path / "mounted-skill"
    shutil.copytree(original, mounted, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("check_saved_output.py", "saved_output_formulas.py", "saved_output_digests.py"):
        assert (mounted / "scripts" / name).read_bytes() == (SCRIPTS / name).read_bytes()
    assert (mounted / "references/saved-output-repair.md").read_bytes() == (
        ROOT / "plugins/llm-accuracy/references/saved-output-repair.md").read_bytes()
    report = tmp_path / "report.md"
    for text, expected, code in (("Cost formula: 1 + 1 = 3.", "fail", 1),
                                 ("Cost formula: 1 + 1 = 2.", "bounded_checks_pass", 0)):
        report.write_text(text, encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(mounted / "scripts/check_saved_output.py"),
                                 str(report), "--version", "v3"], cwd=tmp_path,
                                capture_output=True, text=True, encoding="utf-8", timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        assert result.returncode == code, result.stderr
        assert json.loads(result.stdout)["status"] == expected
        assert report.read_text(encoding="utf-8") == text
