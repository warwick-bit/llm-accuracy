"""Run one advisory hook without shell parsing or interpreter fallback retries."""

import json
import os
import runpy
import sys


def main():
    if sys.version_info < (3, 9):
        print(json.dumps({"systemMessage": "Plugin hooks require Python 3.9 or later; configure a working Python executable."}))
        return 0
    if len(sys.argv) < 2:
        return 0
    name = sys.argv[1]
    if os.path.basename(name) != name or not name.endswith(".py") or name == "hook_runner.py":
        return 0
    target = os.path.join(os.path.dirname(__file__), name)
    if not os.path.isfile(target):
        return 0
    sys.path.insert(0, os.path.dirname(target))
    sys.argv = [target] + sys.argv[2:]
    try:
        runpy.run_path(target, run_name="__main__")
    except SystemExit as error:
        # Exit 2 has blocking semantics in Claude; these plugins are advisory.
        return 1 if error.code == 2 else error.code or 0
    except Exception:
        print(json.dumps({"systemMessage": "Plugin hook unavailable; check Python configuration and package installation."}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

