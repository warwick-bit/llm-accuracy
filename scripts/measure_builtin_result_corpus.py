#!/usr/bin/env python3
"""Count host metadata detections; emit no transcript values or file paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from measure_tool_result_corpus import _content_blocks, _records, _tool_names

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "plugins/llm-accuracy/hooks")
)
from builtin_result_signals import builtin_codes  # noqa: E402


def measure(paths, excluded: list[str]) -> dict:
    report = {
        tool: {
            "results": 0,
            "typed_metadata": 0,
            "candidate_firing": 0,
            "baseline_firing": 0,
        }
        for tool in ("Bash", "Read")
    }
    for path in paths:
        records = _records(path)
        names = _tool_names(records)
        for record in records:
            session = record.get("sessionId")
            if isinstance(session, str) and any(
                part and part in session for part in excluded
            ):
                continue
            if "toolUseResult" not in record:
                continue
            tools = {
                names.get(str(block.get("tool_use_id", "")))
                for block in _content_blocks(record)
                if block.get("type") == "tool_result"
            }
            if len(tools) != 1:
                continue
            tool = next(iter(tools))
            if tool not in report:
                continue
            response = record["toolUseResult"]
            row = report[tool]
            row["results"] += 1
            if isinstance(response, dict):
                if tool == "Bash":
                    row["typed_metadata"] += isinstance(response.get("stdout"), str)
                else:
                    file = response.get("file")
                    row["typed_metadata"] += (
                        response.get("type") == "text"
                        and isinstance(file, dict)
                        and all(
                            type(file.get(k)) is int
                            for k in ("startLine", "numLines", "totalLines")
                        )
                    )
            row["candidate_firing"] += bool(builtin_codes(tool, response))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.home() / ".claude/projects")
    parser.add_argument("--exclude-session", action="append", default=[])
    args = parser.parse_args()
    # Before this change the registration excluded BOTH built-in tools. Baseline
    # firing is therefore zero by registration, not a replayed precision oracle.
    print(
        json.dumps(
            {
                "scope": "builtin_host_metadata",
                "baseline": "mcp_only_registration",
                "counts": measure(
                    sorted(args.root.rglob("*.jsonl")), args.exclude_session
                ),
                "limitation": "detections_not_independently_labelled_precision_or_recall",
            }
        )
    )


if __name__ == "__main__":
    main()
