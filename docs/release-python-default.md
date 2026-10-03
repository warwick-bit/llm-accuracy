# Python executable defaults

Patch versions: LLM Accuracy 0.7.1, Session Ledger 0.3.1 and Evidence Memory
0.5.1. Evidence Memory's Codex manifest stays version-aligned; its separate
POSIX launcher is unchanged.

Each Claude hook plugin now defaults its **Python executable** option to
`python3`. Existing installations with an unset option can upgrade without
manual configuration when that command runs Python 3.9+. Explicit saved values
still take precedence. This replaces the no-default policy in the previous
portability release while preserving direct execution without a shell.

If `python3` is unavailable or unusable, set each installed plugin's option in
`/config` to a verified `python` or absolute executable path, with no arguments,
then reload. A Windows Store alias is not proof of a working installation.
No interpreter discovery or fallback is added. Missing executables remain host
diagnostics; an older Python still receives the existing advisory.

Tests exercise all hook plugins with the shipped default and reject missing or
changed defaults in the compatibility contract. Saved overrides and native
Windows execution remain covered by the existing hook tests and installed QA.

Current evidence: [compatibility matrix](validation/compatibility-candidate.json),
[clean installation smoke](validation/claude-code-smoke-python-default.json),
[unset-option upgrade smoke](validation/python-default-upgrade.json).
Native installed QA is collected by CI. Live coverage is local WSL only;
Desktop, Cowork and live delivery on other operating systems remain unverified.
Hook delivery does not establish factual accuracy.
