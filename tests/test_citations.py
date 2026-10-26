"""References and quotations never certify the surrounding claim's meaning."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/scripts/check_citations.py"


def run_cli(path, expected_exit=0):
    result = subprocess.run([sys.executable, "-B", str(SCRIPT), str(path)], cwd=path.parent.parent,
                            capture_output=True, text=True, timeout=30,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    assert result.returncode == expected_exit, (result.stdout, result.stderr)
    assert result.stderr == ""
    return json.loads(result.stdout)


def test_quotes_resolve_beside_manifest_with_hashes_without_entailment(tmp_path):
    source = tmp_path / "source.txt"
    raw = "Study notes\r\nPrice was mentioned.\r\nNo cause was established.\r\n".encode()
    source.write_bytes(raw)
    manifest = {"sources": {"study": {"path": "source.txt", "url": "https://example.invalid/study"}},
                "citations": [{"id": "q1", "source_id": "study", "claim": "Price caused churn.",
                               "quote": "Price was mentioned.\nNo cause was established."}]}
    path = tmp_path / "citations.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = run_cli(path)
    quote = result["citations"][0]
    assert quote["reference_check"] == "resolved_local_snapshot"
    assert quote["quote_check"] == "found"
    assert quote["first_match"] == {"start_line": 2, "end_line": 3}
    assert quote["claim_support"] == "not_verified"
    assert quote["live_url_status"] == "not_checked"
    assert quote["source_sha256"] == hashlib.sha256(raw).hexdigest()
    assert source.read_bytes() == raw
    source.write_text("Revised: price was not mentioned.", encoding="utf-8")
    revised = run_cli(path)["citations"][0]
    assert revised["quote_check"] == "not_found"
    assert revised["claim_support"] == "not_verified"
    assert revised["source_sha256"] != quote["source_sha256"]


def test_missing_sources_and_url_only_references_do_not_hide_valid_checks(tmp_path):
    (tmp_path / "good.md").write_text("A synthetic observation.", encoding="utf-8")
    manifest = {"sources": {"good": {"path": "good.md"}, "missing": {"path": "missing.txt"},
                            "web": {"url": "https://example.invalid/study"}}, "citations": []}
    for name in ("good", "missing", "web", "undeclared"):
        manifest["citations"].append({"id": name, "source_id": name,
                                      "claim": "A synthetic observation.", "quote": "A synthetic observation."})
    manifest["citations"].append({"id": "no_quote", "source_id": "good", "claim": "A paraphrase"})
    path = tmp_path / "citations.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    rows = run_cli(path)["citations"]
    assert [row["reference_check"] for row in rows] == ["resolved_local_snapshot", "unavailable",
                                                       "needs_host_retrieval", "unresolved", "resolved_local_snapshot"]
    assert [row["quote_check"] for row in rows] == ["found", "not_checked", "not_checked", "not_checked", "not_requested"]
    assert all(row["claim_support"] == "not_verified" for row in rows)


@pytest.mark.parametrize("invalid", ["duplicate_key", "duplicate_id", "empty_quote", "wrong_shape"])
def test_ambiguous_citation_manifest_is_rejected(tmp_path, invalid):
    manifest = {"sources": {}, "citations": [{"id": "one", "source_id": "missing", "claim": "A claim"}]}
    if invalid == "duplicate_id":
        manifest["citations"] *= 2
    elif invalid == "empty_quote":
        manifest["citations"][0]["quote"] = ""
    elif invalid == "wrong_shape":
        manifest["sources"] = []
    raw = json.dumps(manifest)
    if invalid == "duplicate_key":
        raw = raw.replace('"sources": {}', '"sources": {}, "sources": {}')
    path = tmp_path / "citations.json"
    path.write_text(raw, encoding="utf-8")
    assert run_cli(path, 2)["execution"] == "error"
