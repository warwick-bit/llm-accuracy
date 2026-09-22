"""Read additive, literal trigger phrases from user-owned configuration.

No writes, network access, regex execution from config, or user-content logging.
The default file is outside the installed plugin cache. Configuration errors
leave built-in checks active and emit only a fixed diagnostic code to stderr.
"""

from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path


CONFIG_ENV = "LLM_ACCURACY_CONFIG"
FAMILIES = frozenset({"claim_fidelity", "analysis", "fusion_evidence"})
MAX_CONFIG_BYTES = 32_768
MAX_PHRASES_PER_FAMILY = 64
MAX_PHRASE_CHARS = 120


def trigger_lists(payload: object) -> dict[str, list[str]]:
    """Validate the entire config before allowing any custom trigger."""
    if not isinstance(payload, dict) or set(payload) - {
        "schema_version",
        "extra_triggers",
    }:
        raise ValueError("invalid_config")
    version = payload.get("schema_version", 1)
    if type(version) is not int or version != 1:
        raise ValueError("invalid_config")
    families = payload.get("extra_triggers", {})
    if not isinstance(families, dict) or set(families) - FAMILIES:
        raise ValueError("invalid_config")
    for phrases in families.values():
        if not isinstance(phrases, list) or len(phrases) > MAX_PHRASES_PER_FAMILY:
            raise ValueError("invalid_config")
        for phrase in phrases:
            if (
                not isinstance(phrase, str)
                or len(phrase) > MAX_PHRASE_CHARS
                or not any(char.isalnum() for char in phrase)
            ):
                raise ValueError("invalid_config")
    return families


def read_triggers() -> dict[str, list[str]]:
    """Read a bounded regular file; never include paths or contents in errors."""
    override = os.environ.get(CONFIG_ENV)
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    path = Path(override).expanduser() if override else root / "llm-accuracy.json"
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("not_regular_file")
        with path.open("rb") as source:
            raw = source.read(MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise ValueError("oversized_config")
        return trigger_lists(json.loads(raw.decode("utf-8-sig")))
    except FileNotFoundError:
        code = "config_unavailable" if override else ""
    except (OSError, ValueError, RecursionError):
        code = "invalid_config"
    if code:
        print(f"LLM Accuracy: {code}; built-in checks remain active.", file=sys.stderr)
    return {}


def custom_trigger_matches(family: str, prompt: str) -> bool:
    """Match whole literal phrases, ignoring case and repeated whitespace."""
    normalized = " ".join(prompt.casefold().split())
    for phrase in read_triggers().get(family, []):
        literal = re.escape(" ".join(phrase.casefold().split()))
        if re.search(r"(?<!\w)" + literal + r"(?!\w)", normalized):
            return True
    return False
