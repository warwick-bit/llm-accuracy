#!/usr/bin/env python3
"""Post-compaction accuracy nudge, injected via SessionStart(compact).

Claude Code does not inject PostCompact hook output into context, so this
nudge runs on the SessionStart event with the "compact" matcher instead.
"""

from __future__ import annotations

import json
import sys


CONTEXT = (
    "Post-compaction accuracy nudge: re-read exact values before asserting counts, IDs, dates, "
    "SHAs, statuses, file paths, metric definitions, or task completion. Self-audit any "
    "load-bearing claim you are about to restate from memory, and downgrade claims whose current "
    "source has not been rechecked."
)


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
        source = payload.get("source") if isinstance(payload, dict) else None
        if source is not None and source != "compact":
            return 0
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
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
