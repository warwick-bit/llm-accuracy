# Platform compatibility candidate (unreleased)

Accuracy 0.7.0, Session Ledger 0.3.0 and Evidence Memory 0.4.0 change Claude hook
launching to direct executable/argument vectors. Use Claude Code 2.1.287+ and
configure each plugin's Python executable before restarting or reloading. Native
Windows command execution no longer needs Git Bash; installed Windows/macOS
delivery remains unverified. This adds an explicit setup step on upgrade;
the previous automatic command-name selection is not retained for Claude.

The doctor probes executable usability/version and shipped exec registrations.
Ledger skills avoid POSIX-only automatic preprocessing. Windows memory restore
packets expose shell-independent argument vectors and label legacy PowerShell
prefixes. Codex keeps a separate experimental
POSIX manifest and now checks interpreter usability before running a hook once.

Evidence Memory distinguishes lock contention from capture I/O failures. Ordinary
overlap defers quietly and preserves the cursor; final capture/restore gets a
bounded wait and a fixed diagnostic if still busy. No persistence schema,
capture scope, expiry or stop/clear boundaries change.

Release gates cover native Windows without Git Bash and reject missing/skipped
mandatory cases. Current candidate source hashes bind installed-host receipts;
Linux/WSL, Windows, macOS and Desktop modes must remain explicit. Historical
receipts are not reused. Read [the compatibility contract](COMPATIBILITY.md)
and [current outcomes](validation/compatibility-candidate.json) before claiming
installed-host support. Main is the marketplace delivery branch. Its required
publication check holds package changes until all nine targets pass: Linux/WSL,
macOS, both Windows Bash scenarios, and Chat/Cowork on Windows/macOS. This
candidate remains on hold while required installed QA is missing.

Desktop Chat remains skills-only; Cowork supports only the stateless packages
here, with candidate hook delivery unverified. Desktop Code UI is separately
unverified; terminal receipts do not certify it. Native Codex without a POSIX
hook shell is unsupported.
