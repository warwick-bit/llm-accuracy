#!/usr/bin/env python3
"""Compatibility CLI for the packaged numerical-claims checker."""
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[1] /
                      "plugins/llm-accuracy/scripts/check_numerical_claims.py"),
                   run_name="__main__")
