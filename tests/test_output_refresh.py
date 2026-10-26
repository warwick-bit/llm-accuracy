"""Consumer checks for observed failed refreshes, required files and preserved bytes."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/scripts/check_output_refresh.py"


def invoke(*args, expected=0):
    p = subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)], capture_output=True,
                       text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert p.returncode == expected, (p.stdout, p.stderr)
    assert not p.stderr
    return json.loads(p.stdout)


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "input.json").write_text('[100, 200]', encoding="utf-8")
    (root / "totals.csv").write_bytes(b"total\n300\n")
    (root / "report.md").write_bytes(b"The total is 300.\n")
    manifest, baseline = tmp_path / "manifest.json", tmp_path / "before.json"
    manifest.write_text(json.dumps({"inputs": ["input.json"], "outputs": ["report.md", "totals.csv"]}), encoding="utf-8")
    baseline.write_text(json.dumps(invoke("capture", root, manifest)), encoding="utf-8")
    return root, manifest, baseline


def check(workspace, outcome="failed"):
    root, manifest, baseline = workspace
    return invoke("check", root, manifest, "--before", baseline, "--outcome", outcome)


def producer(root, safe=False):
    # A real child writes one output and then crashes on empty input; safe variant validates first.
    program = """import json
from pathlib import Path
values = json.loads(Path('input.json').read_text())
if SAFE and not values:
    raise SystemExit(3)
Path('totals.csv').write_text('total\\n' + str(sum(values)) + '\\n')
if not values:
    raise SystemExit(3)
Path('report.md').write_text('The total is ' + str(sum(values)) + '.\\n')
""".replace("SAFE", repr(safe))
    return subprocess.run([sys.executable, "-c", program], cwd=root, capture_output=True,
                          timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).returncode


def test_real_partial_refresh_detects_mixed_outputs_and_retains_original_snapshot(workspace):
    root, _, baseline = workspace
    original = baseline.read_bytes()
    (root / "input.json").write_bytes(b"[]")
    assert producer(root) == 3
    result = check(workspace)
    assert result["input_change"] == "changed"
    assert result["output_preservation"] == "changed"
    assert result["changed_paths"]["outputs"] == ["totals.csv"]
    assert result["required_outputs"] == "all_readable"  # Presence alone misses this defect.
    assert baseline.read_bytes() == original
    assert (root / "report.md").read_bytes() == b"The total is 300.\n"


def test_failure_before_publication_preserves_complete_output_set(workspace):
    root, _, _ = workspace
    (root / "input.json").write_bytes(b"[]")
    original = {path: path.read_bytes() for path in root.iterdir()}
    assert producer(root, safe=True) == 3
    result = check(workspace)
    assert result["input_change"] == "changed"
    assert result["output_preservation"] == "preserved"
    assert result["changed_paths"]["outputs"] == []
    assert all(path.read_bytes() == raw for path, raw in original.items())


def test_successful_changed_input_and_identical_valid_output_are_distinct_observations(workspace):
    root, _, _ = workspace
    (root / "input.json").write_bytes(b"[110, 200]")
    assert producer(root) == 0
    result = check(workspace, "succeeded")
    assert result["input_change"] == "changed"
    assert result["output_preservation"] == "not_applicable"
    assert set(result["changed_paths"]["outputs"]) == {"report.md", "totals.csv"}
    # A different allocation with the same total is legitimate, not evidence of stale output.
    (root / "input.json").write_bytes(b"[90, 210]")
    assert producer(root) == 0
    # Restore the fixture's LF bytes (Windows text-mode line endings are a real byte change).
    for name in ("report.md", "totals.csv"):
        path = root / name
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    result = check(workspace, "succeeded")
    assert result["input_change"] == "changed"
    assert result["changed_paths"]["outputs"] == []


def test_deleted_output_is_not_preserved_and_success_cannot_hide_missing_file(workspace):
    root, _, _ = workspace
    (root / "report.md").unlink()
    assert check(workspace)["output_preservation"] == "changed"
    assert check(workspace, "succeeded")["required_outputs"] == "incomplete_or_unavailable"


def test_resolved_path_cannot_read_outside_workspace(workspace):
    root, _, _ = workspace
    target = root.parent / "outside.txt"
    target.write_bytes(b"outside")
    (root / "report.md").unlink()
    try:
        (root / "report.md").symlink_to(target)
    except OSError:
        pytest.skip("Symlink privilege unavailable")
    result = check(workspace)
    assert result["after"]["outputs"]["report.md"] == {"status": "unavailable"}
    assert result["output_preservation"] == "not_verified"


def test_missing_baseline_or_unreadable_current_file_cannot_pass_preservation(workspace):
    root, manifest, baseline = workspace
    (root / "report.md").unlink()
    baseline.write_text(json.dumps(invoke("capture", root, manifest)), encoding="utf-8")
    assert check(workspace)["output_preservation"] == "not_verified"
    (root / "report.md").mkdir()
    assert check(workspace)["after"]["outputs"]["report.md"]["status"] == "unavailable"
    assert check(workspace)["output_preservation"] == "not_verified"


def test_empty_output_is_explicit_and_reordered_manifest_keeps_equivalent_requirements(workspace):
    root, manifest, baseline = workspace
    (root / "report.md").write_bytes(b"")
    baseline.write_text(json.dumps(invoke("capture", root, manifest)), encoding="utf-8")
    manifest.write_text('{"outputs":["totals.csv","report.md"],"inputs":["input.json"]}', encoding="utf-8")
    result = check(workspace)
    assert result["output_preservation"] == "preserved"
    assert result["empty_outputs"] == ["report.md"]
    (root / "input.json").unlink()
    assert check(workspace)["input_change"] == "not_verified"


@pytest.mark.parametrize("defect", ["missing_row", "extra_row", "bad_hash", "negative_bytes", "bool_version", "missing_requirements", "duplicate_key"])
def test_malformed_or_incomplete_snapshot_is_rejected(workspace, defect):
    root, manifest, baseline = workspace
    data = json.loads(baseline.read_bytes())
    if defect == "missing_row":
        del data["outputs"]["report.md"]
    elif defect == "extra_row":
        data["outputs"]["extra"] = {"status": "missing"}
    elif defect == "bad_hash":
        data["outputs"]["report.md"]["sha256"] = "wrong"
    elif defect == "negative_bytes":
        data["outputs"]["report.md"]["bytes"] = -1
    elif defect == "bool_version":
        data["schema_version"] = True
    elif defect == "missing_requirements":
        data["requirements"]["outputs"] = ["report.md"]
    raw = json.dumps(data) if defect != "duplicate_key" else '{"schema_version":1,"schema_version":1}'
    baseline.write_text(raw, encoding="utf-8")
    assert invoke("check", root, manifest, "--before", baseline, "--outcome", "failed", expected=2)["execution"] == "error"


@pytest.mark.parametrize("paths", [["../outside"], ["/absolute"], ["C:/file"], ["report.md", "REPORT.md"], ["input.json"], []])
def test_unsafe_or_ambiguous_requirements_are_rejected(workspace, paths):
    root, manifest, _ = workspace
    manifest.write_text(json.dumps({"inputs": ["input.json"], "outputs": paths}), encoding="utf-8")
    assert invoke("capture", root, manifest, expected=2)["execution"] == "error"
