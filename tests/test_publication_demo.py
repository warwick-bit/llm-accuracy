"""Consumer checks for the optional demo, using newly authored fictional data."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/publication_demo.py"
spec = importlib.util.spec_from_file_location("publication_demo", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
ORIGINAL = {"invoices": [
    {"customer": "C-10", "cents": 12500, "status": "issued"},
    {"customer": "C-10", "cents": -2500, "status": "issued"},
    {"customer": "C-20", "cents": 4500, "status": "issued"},
    {"customer": "C-30", "cents": 99900, "status": "cancelled"},
]}


def cli(*arguments, success=True):
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, arguments)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == (0 if success else 1), (result.stdout, result.stderr)
    return json.loads(result.stdout)


def source_file(tmp_path, source):
    path = tmp_path / "source.json"
    path.write_bytes(demo.json_bytes(source))
    return path


def cancelled():
    source = copy.deepcopy(ORIGINAL)
    for row in source["invoices"]:
        row["status"] = "cancelled"
    return source


def documents(summary, report=None):
    return {"summary.json": demo.json_bytes(summary),
            "report.csv": demo.report_bytes(summary) if report is None else report}


def test_original_and_changed_input_from_separate_process(tmp_path):
    root = tmp_path / "bundle"
    source = source_file(tmp_path, ORIGINAL)
    before = source.read_bytes()
    cli("refresh", source, root)
    original = cli("read", root)
    assert original["summary"] == {"C-10": 10000, "C-20": 4500}
    assert original["report"] == "customer,aud\nC-10,100.00\nC-20,45.00\n"
    assert source.read_bytes() == before
    changed = copy.deepcopy(ORIGINAL)
    changed["invoices"][0]["cents"] = 7500
    source_file(tmp_path, changed)
    cli("refresh", source, root)
    current = cli("read", root)
    assert current["summary"] == {"C-10": 5000, "C-20": 4500}
    assert current["report"] == "customer,aud\nC-10,50.00\nC-20,45.00\n"
    assert current["generation"] != original["generation"]

    # Legitimate empty, zero and credit refreshes remain supported.
    path = source_file(tmp_path, cancelled())
    cli("refresh", path, root)
    empty = cli("read", root)
    assert empty["summary"] == {} and empty["report"] == "customer,aud\n"
    source = {"invoices": [
        {"customer": "C-10", "cents": 0, "status": "issued"},
        {"customer": "C-20", "cents": -150, "status": "issued"},
    ]}
    source_file(tmp_path, source)
    cli("refresh", path, root)
    result = cli("read", root)
    assert result["summary"] == {"C-10": 0, "C-20": -150}
    assert result["report"] == "customer,aud\nC-10,0.00\nC-20,-1.50\n"

def test_empty_producer_failure(tmp_path):
    root = tmp_path / "bundle"
    source = source_file(tmp_path, ORIGINAL)
    cli("refresh", source, root)
    old = cli("read", root)
    source_file(tmp_path, cancelled())
    error = cli("refresh", source, root, "--simulate-empty-report-failure", success=False)
    assert error["error"] == "simulated report failure after numerical output"
    assert cli("read", root) == old
    incomplete = [p for p in (root / "generations").iterdir() if not (p / "report.csv").exists()]
    assert len(incomplete) == 1
    assert json.loads((incomplete[0] / "summary.json").read_bytes()) == {}
    # Restore the unsafe direct-write behavior using the same producer steps.
    loose = tmp_path / "loose"
    loose.mkdir()
    for name, data in documents(old["summary"]).items():
        (loose / name).write_bytes(data)
    (loose / "summary.json").write_bytes(demo.json_bytes(demo.summarize(cancelled())))
    with pytest.raises(RuntimeError, match="simulated report failure"):
        (loose / "report.csv").write_bytes(demo.report_bytes({}, simulate_empty_failure=True))
    mixed = {name: (loose / name).read_bytes() for name in demo.DOCUMENTS}
    assert json.loads(mixed["summary.json"]) == {}
    assert mixed["report.csv"] == old["report"].encode()
    with pytest.raises(ValueError, match="bindings disagree"):
        demo.validate(mixed)


def test_binding_variants():
    summary = {"C-10": 10000, "C-20": 4500}
    # Semantic alternative: reorder rows, use CRLF and equivalent signed amounts.
    demo.validate(documents(summary, b"customer,aud\r\nC-20,+45.00\r\nC-10,100.00\r\n"))
    for report in (
        b"customer,aud\nC-20,100.00\nC-10,45.00\n",  # label swap
        b"customer,aud\nC-10,100.01\nC-20,45.00\n",  # changed amount
        b"customer,aud\nC-10,100.00\n",  # missing
        b"customer,aud\nC-10,100.00\nC-20,45.00\nC-30,0.00\n",  # extra
    ):
        with pytest.raises(ValueError, match="bindings disagree"):
            demo.validate(documents(summary, report))
    with pytest.raises(ValueError, match="duplicate"):
        demo.validate(documents(summary, b"customer,aud\nC-10,100.00\nC-10,100.00\n"))
    with pytest.raises(ValueError, match="Unsupported report schema"):
        demo.validate(documents(summary, b"All customers were checked.\n"))
    # Two agreeing wrong documents pass: this check is not source truth.
    demo.validate(documents({"C-10": 99999}))


def test_invalid_candidate_and_post_switch_exception(tmp_path, monkeypatch):
    demo.refresh(tmp_path, ORIGINAL)
    old = cli("read", tmp_path)
    with monkeypatch.context() as patch:
        patch.setattr(demo, "report_bytes", lambda *args: old["report"].encode())
        with pytest.raises(ValueError, match="bindings disagree"):
            demo.refresh(tmp_path, cancelled())
    assert cli("read", tmp_path) == old
    replace = demo.os.replace

    def replace_then_fail(source, destination):
        replace(source, destination)
        raise RuntimeError("exception after switch")

    monkeypatch.setattr(demo.os, "replace", replace_then_fail)
    with pytest.raises(RuntimeError, match="after switch"):
        demo.refresh(tmp_path, cancelled())
    new = cli("read", tmp_path)
    assert new["summary"] == {} and new["report"] == "customer,aud\n"
    assert new["generation"] != old["generation"]


def test_reader_pinning_and_bypass(tmp_path):
    demo.refresh(tmp_path, ORIGINAL)
    old = cli("read", tmp_path)
    demo.refresh(tmp_path, cancelled())
    new = cli("read", tmp_path)
    assert cli("read", tmp_path, "--generation", old["generation"]) == old
    assert new["summary"] == {} and new["report"] == "customer,aud\n"
    with pytest.raises(ValueError, match="bindings disagree"):
        demo.validate(documents(old["summary"], new["report"].encode()))
    # Byte integrity is checked on this same reader path.
    generation = demo.refresh(tmp_path, ORIGINAL)
    folder = demo.generation_dir(tmp_path, generation)
    hashes = json.loads((folder / "manifest.json").read_bytes())
    assert hashes == {name: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                      for name in demo.DOCUMENTS}
    # Newline-only changes preserve CSV meaning, but must invalidate byte evidence.
    path = folder / "report.csv"
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert cli("read", tmp_path, success=False)["error"] == "Published bytes changed"
