"""Regression tests for the private-preview distribution gate."""

from __future__ import annotations

from pathlib import Path

from scripts.check_private_preview_boundary import boundary_violations


ROOT = Path(__file__).resolve().parents[1]


def test_current_plugin_satisfies_boundary() -> None:
    assert boundary_violations(ROOT / "plugins" / "llm-accuracy") == []


def test_session_ledger_plugin_satisfies_its_local_only_boundary() -> None:
    assert (
        boundary_violations(
            ROOT / "plugins" / "session-ledger", profile="session-ledger"
        )
        == []
    )


def test_session_ledger_profile_still_rejects_external_verification_artifacts(
    tmp_path: Path,
) -> None:
    (tmp_path / "verify-number.py").write_text("pass\n", encoding="utf-8")

    assert boundary_violations(tmp_path, profile="session-ledger") == [
        "excluded artifact: verify-number.py"
    ]


def test_session_ledger_extension_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "session_ledger.py").write_text("pass\n", encoding="utf-8")

    assert boundary_violations(tmp_path) == ["excluded artifact: session_ledger.py"]


def test_non_text_artifact_is_rejected_cleanly(tmp_path: Path) -> None:
    (tmp_path / "icon.png").write_bytes(b"\xff\xd8\xff")

    assert boundary_violations(tmp_path) == ["unexpected non-text artifact: icon.png"]


def test_symlink_is_rejected_before_its_target_is_read(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-preview-artifact.md"
    outside.write_text("private source", encoding="utf-8")
    (tmp_path / "linked.md").symlink_to(outside)

    assert boundary_violations(tmp_path) == ["symlink artifact: linked.md"]


def test_docs_may_discuss_disallowed_commands(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(
        "Do not use subprocess or curl in this plugin.\n", encoding="utf-8"
    )

    assert boundary_violations(tmp_path) == []


def test_python_network_import_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "hook.py").write_text("import subprocess\n", encoding="utf-8")

    assert boundary_violations(tmp_path) == ["network-capable import: hook.py"]
