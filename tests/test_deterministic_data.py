"""Contract tests for the editable deterministic-data template."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "deterministic-data"
EXAMPLE = PLUGIN / "catalogues" / "example.catalogue.json"
VALIDATOR = PLUGIN / "scripts" / "validate_catalogue.py"


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_catalogue", VALIDATOR)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example() -> dict[str, object]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_example_catalogue_is_structurally_valid() -> None:
    assert load_validator().validate_catalogue(example()) == []


def test_catalogue_schema_encodes_cli_portable_constraints() -> None:
    schema = json.loads(
        (PLUGIN / "references" / "catalogue.schema.json").read_text(encoding="utf-8")
    )
    definition = schema["properties"]["definitions"]["items"]

    assert definition["properties"]["definition_id"]["pattern"]
    assert len(definition["allOf"]) == 2


def test_duplicate_alias_is_rejected() -> None:
    catalogue = example()
    catalogue["definitions"][1]["aliases"] = [" ACTIVE   UNITS "]
    assert "alias_duplicate" in load_validator().validate_catalogue(catalogue)


def test_approved_definition_requires_a_binding() -> None:
    catalogue = example()
    catalogue["definitions"][0]["source_binding"] = None
    assert "approved_without_source_binding" in load_validator().validate_catalogue(
        catalogue
    )


def test_candidate_cannot_have_a_binding() -> None:
    catalogue = example()
    catalogue["definitions"][1]["source_binding"] = {
        "adapter_id": "synthetic",
        "query_id": "synthetic",
    }
    assert "nonapproved_with_source_binding" in load_validator().validate_catalogue(
        catalogue
    )


def test_catalogue_cli_does_not_echo_values(tmp_path: Path) -> None:
    catalogue = example()
    secret = "CANARY-CATALOGUE-VALUE-MUST-NOT-ECHO"
    catalogue["definitions"][0]["aliases"] = [secret, secret]
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps(catalogue), encoding="utf-8")

    result = subprocess.run(
        ["python3", str(VALIDATOR), str(path)],
        capture_output=True,
        check=False,
        text=True,
    )

    output = json.loads(result.stdout)
    assert result.returncode == 1
    assert output["authority"] == "structure_only"
    assert secret not in result.stdout


def test_docs_make_user_ownership_and_data_boundary_explicit() -> None:
    readme = (PLUGIN / "README.md").read_text(encoding="utf-8")
    skill = (PLUGIN / "skills" / "data-routing" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    normalized_skill = " ".join(skill.split())

    assert "Fork or copy this repository" in readme
    assert "Do not edit an installed marketplace cache" in readme
    assert "Never put credentials" in readme
    assert "user-owned catalogue" in skill
    assert "Return one evidence receipt inline" in skill
    assert "Do not write the receipt to a file" in skill
    assert "Structural validation" in skill
    assert "same response before any canonical value" in normalized_skill
    assert "must contain exactly" in normalized_skill
    assert "A routing summary or a different" in normalized_skill
    assert "`claim_status` to `withheld`" in skill
    assert "`source_refs`: a non-empty list" in skill
    assert "`freshness`, `completeness`, and `conflict`" in skill
    assert "any completed nonzero" in normalized_skill
    assert "could not be launched" in normalized_skill
    output = skill.split("## Output", 1)[1]
    assert output.index("Evidence receipt") < output.index("Canonical value")
