# Compatibility and release evidence

The source candidate uses shell-independent Claude hooks. Each hook plugin
requires Claude Code **2.1.287 or later** and a configured, working **Python
3.9 or later** executable. This is a conservative host floor verified by the
maintainer, not a claim about the first version that introduced exec hooks.
The native Windows implementation does not require Git Bash. Installed Windows
and macOS delivery remain unverified until their current smoke receipts pass;
these are candidate support targets, not certified installations.
WSL uses its Linux Python installation;
native Windows uses Windows Python. Do not point one runtime at the other's
launcher. A `.cmd`/`.bat` shim or `py -3` is not an executable name: configure
the actual Python executable, with no arguments.

## OS and host boundaries

- **Claude Code terminal/IDE, including Desktop's local Code mode:** Linux,
  WSL, native Windows and macOS use the same exec-form registrations. CI checks
  shipped commands on Linux, Windows with and without Git Bash, and macOS.
  Automated Python tests do not establish installation or delivery in a real
  Claude session. See the current candidate receipt for installed-host results.
- **Claude Desktop Chat / web chat:** skills-only. No hooks, doctor execution,
  local ledger or evidence capture. Accuracy and Deterministic Data provide
  instructions; executing a local validator requires a separate capable host.
  Desktop itself is a Windows/macOS product; WSL/Linux users use Code or web.
- **Cowork on Windows/macOS:** stateless Accuracy and Deterministic Data only.
  Hook capability exists, but the candidate's installed delivery remains
  unverified until a current smoke is recorded. Do not assume a configured
  desktop Python exists inside Cowork's execution environment. Session Ledger
  and Evidence Memory are unsupported here.
- **Codex Evidence Memory:** a separate experimental POSIX package, for
  Linux/WSL/macOS and Windows only when its hook runtime supplies a POSIX shell.
  It uses a usability probe, not Claude's user configuration substitution.
  Native Codex without a POSIX hook shell is unsupported. The Claude native
  Windows gate does not establish native Codex support. Other packages remain
  Claude-only. CLI access and the current installed capture state must be
  checked before relying on memory.

## Configure Python before starting a session

Each installed hook plugin has a required **Python executable** option with no
platform-dependent default. Set it when
enabling the plugin or in `/config`. On Linux/WSL/macOS use a verified `python3`;
on native Windows use a verified `python` or the absolute `python.exe` path.
Windows Store aliases can exist without a working installation. Execute the
candidate's `--version`, then configure the command that actually works.
An unavailable interpreter produces a host diagnostic; it must not block a
turn. An older Python produces a fixed advisory rather than loading hooks.

For headless installation, use `claude plugin configure PLUGIN@llm-accuracy
--values-stdin` and supply a JSON object containing `python_executable` through
stdin. Use shell-appropriate quoting for paths. `--plugin-dir` alone does not
populate saved options; enabling requires explicit interpreter configuration.

The Accuracy doctor accepts `--python-executable NAME_OR_PATH` and runs the
shipped exec registrations without a shell. Its default is its own running
interpreter, explicitly labelled `doctor_process`. It does not infer the
installed plugin's saved option or current-session activation. Its isolated
`--live` probe supplies a non-secret interpreter option for the candidate.

## Release guardrails

`docs/validation/compatibility-candidate.json` is a raw-free record bound to the
version and SHA-256 of every package's source tree. Every required OS/host cell
must say `pass` or `untested`. A pass needs a host version and all required QA
checks. Historical receipts cannot establish a current candidate's support.

After changing any package file, run `python3 scripts/check_compatibility.py
--write-candidate` to reset all installed-host outcomes to `untested`. Perform
the actual QA before replacing an outcome. Do not carry forward a pass or edit
its hash to fit new source. Run the checker in every PR; before a release run
it with `--release`, which additionally requires clean installed Code smokes on
Linux, WSL, native Windows and macOS. A WSL pass cannot certify Windows or macOS.
Tag builds run the release check. Missing, stale or incomplete evidence fails
the check. Explicit untested cells are coverage gaps, never support proof.

The required combined `release-gates` check includes Linux Python 3.9–3.14,
native Windows Python 3.9/3.14, Git Bash Windows controls, and macOS. The native
gate verifies mandatory hook cases were present and not skipped. Keep that
combined check required in branch protection when editing workflow names.

## Installed-host QA

Use a clean temporary profile and synthetic prompts/results only. Record the
host version and Python version, source binding and outcome, without raw logs.

1. Install through the marketplace; verify package versions and source bytes.
   Do not use `--plugin-dir` as the installed-plugin test.
2. Configure Python, reload, and prove prompt-hook delivery in a fresh session.
   Exercise a path containing spaces/apostrophes/Unicode. Check an invalid
   executable is advisory; restore configuration and prove delivery again.
3. Upgrade from the previous package and verify saved options, capture cutoff,
   pause/clear boundaries and exactly-once persistence remain intact.
4. Uninstall and verify registration removal. For persistence, check default
   data deletion and deliberate `--keep-data` retention separately.
5. Repeat native Windows without Git Bash, Windows with Git Bash, Linux/WSL
   and macOS. For Desktop, record **Chat**, **Code** or **Cowork** separately;
   a Chat skills test cannot certify a Cowork hook. Confirm Chat never claims
   it captured or retrieved local memory. Leave unavailable targets untested.

Official host contracts: [exec hooks](https://code.claude.com/docs/en/hooks),
[plugin configuration](https://code.claude.com/docs/en/plugins-reference),
and [plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

## Evidence Memory contention

Overlapping ordinary hooks defer quietly when the session lock is busy. They
leave the cursor untouched; the next capture or explicit `sync TRANSCRIPT_PATH`
retries the same source. Restore, Stop and PreCompact wait at most 0.5 seconds
for the lock, then emit a fixed advisory if still busy. A final deferred capture
may need explicit sync; a restore that remains busy cannot inject its packet.
`status`/`sync` report `memory_session_lock_busy` (including read-only status).
Persistent failures inside capture still emit diagnostics. Never delete a lock
file to bypass contention: a file's existence does not mean its lock is held.
