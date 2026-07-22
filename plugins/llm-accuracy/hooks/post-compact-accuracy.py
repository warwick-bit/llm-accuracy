#!/usr/bin/env python3
"""Claude-only PostCompact nudge for load-bearing accuracy checks."""

from __future__ import annotations

import json


CONTEXT = (
    "Post-compaction accuracy nudge: re-read exact values before asserting counts, IDs, dates, "
    "SHAs, statuses, file paths, metric definitions, or task completion. Self-audit any "
    "load-bearing claim you are about to restate from memory, and downgrade claims whose current "
    "source has not been rechecked."
)


def main() -> int:
    try:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostCompact",
                        "additionalContext": CONTEXT,
                    }
                }
            )
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
