"""Hook tests use the host POSIX shell, including explicit Git Bash on Windows."""

import os

HOOK_SHELL = os.environ.get("HOOK_TEST_SHELL", "/bin/sh" if os.name == "posix" else "")
