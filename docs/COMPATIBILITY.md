# Compatibility and release evidence

The source candidate requires Claude Code **2.1.287 or later** and working
**Python 3.9 or later**. Python is discovered automatically: a saved executable
override takes precedence; otherwise the launcher probes `python3`, `python`,
then `py -3`. Failed probes and unsupported Python versions are skipped.
POSIX uses `sh`; native Windows uses PowerShell when Git Bash is absent.
No additional shell or Node installation is required. WSL uses Linux Python;
native Windows uses Windows Python. Current installed-host evidence remains
bound to the candidate's package bytes; historical passes do not certify it.

## OS and host boundaries

- **Claude Code terminal/IDE:** Linux,
  WSL, native Windows and macOS use the same shell-form registrations. CI checks
  shipped commands on Linux, Windows with and without Git Bash, and macOS.
  Automated Python tests do not establish installation or delivery in a real
  Claude session. See the current candidate receipt for installed-host results.
- **Desktop's local Code mode:** candidate only; UI delivery is unverified.
  A terminal Code receipt does not certify this UI.
- **Claude Desktop Chat / web chat:** experimental skills-only. No hooks, doctor execution,
  local ledger or evidence capture. Accuracy and Deterministic Data provide
  instructions; executing a local validator requires a separate capable host.
  Desktop exists on Windows/macOS and Linux beta; each UI needs its own receipt.
  On WSL, use the Windows Desktop application for Desktop sessions.
- **Cowork on Windows/macOS/Linux beta:** experimental stateless Accuracy and Deterministic Data only.
  Candidate hook delivery remains unverified. A stateless skills receipt does
  not certify hooks or Python execution. Do not assume a configured
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

Each hook plugin has an optional **Python executable** override. Leave it empty
for automatic discovery. Set a working executable name or absolute path, without
arguments, only when choosing a particular installation. Saved overrides survive
updates and are honored even when Python is absent from PATH. An invalid saved
override produces an advisory; correct or clear it rather than silently using a
different interpreter. Windows Store aliases and Python below 3.9 fail the
usability probe. Hooks execute once after a successful probe; hook errors never
trigger another interpreter attempt. Launchers preserve UTF-8 stdin and paths.

Hooks use a shared batch/POSIX dispatcher. The shell command sets a fixed target,
then sources the dispatcher inside parentheses: POSIX skips the batch section;
Windows PowerShell invokes it through cmd.exe and runs Python directly.
The outer command exits zero so a missing launcher cannot block a prompt.
Option values travel only through the host-exported
`CLAUDE_PLUGIN_OPTION_PYTHON_EXECUTABLE`, never through shell interpolation.

For headless override configuration, use `claude plugin configure
PLUGIN@llm-accuracy --values-stdin` with a JSON object containing
`python_executable`. Setting an empty string restores discovery. `--plugin-dir`
requires no saved option for discovery. Skills that invoke Python directly must
resolve a working executable before constructing their argument vector.

The Accuracy doctor accepts `--python-executable NAME_OR_PATH` and probes the
shipped shell registrations. Its default is its own running interpreter,
explicitly labelled `doctor_process`. It does not infer the installed plugin's
saved option or current-session activation. Its isolated `--live` probe supplies
a non-secret interpreter override for the candidate.

## Release guardrails

`docs/validation/compatibility-candidate.json` is a raw-free record bound to the
version and SHA-256 of every package's source tree. Every required OS/host cell
must say `pass` or `untested`. A pass needs a host version and all required QA
checks, its own package source bindings, and a supported Python version for Code.
Every pass also needs its actual `platform` and `host_kind`, matching the target.
Code uses `code`; Desktop uses `desktop_chat` or `cowork`. Platform labels are
`Linux`, `Linux/WSL`, `Windows` or `Darwin` (macOS). Copying a WSL receipt into a
Mac/Linux row or a Chat receipt into Cowork fails this consistency check.
These are maintainer QA records, not an independently authenticated test oracle.
Historical receipts cannot establish a current candidate's support.

Every pass row is sealed to one QA run. `source_commit` names the full commit
the run tested; after a squash merge that commit may be reachable only from the
pull request, not from `main`. `row_sha256` is the SHA-256 of the row's other
fields as canonical JSON (sorted keys, no whitespace). The checker recomputes
the seal, so a field edited after recording fails. So does a row that Git merged
from two runs: if two branches each record the same target, they both change
the seal lines and the merge stops. Resolve that conflict with
`--write-candidate` and a fresh run on the merged source, never by picking a
side. Record passes with `scripts/record_compatibility_pass.py`; never write or
edit a seal by hand. The seal detects accidental splices and edits; like the
rest of this record, it is not an authentication mechanism.

After changing any package file, run `python3 scripts/check_compatibility.py
--write-candidate` to reset all installed-host outcomes to `untested`. Perform
the actual QA before replacing an outcome. Do not carry forward a pass or edit
its hash to fit new source. Run the checker in every PR; before a release run
it with `--release`, which requires all four native installation targets
(Linux/macOS/Windows with and without Bash) plus at least one genuine current-source
live Code pass. Schema 5 fixes this support policy and sealed pass rows. Separate `native_installations`
rows use `installed` or `untested`; they require exact OS/host, versions, package
bindings, checks (`clean_install`, `configured_python`, `automatic_python_upgrade`,
`automatic_python_fresh`, `upgrade`, `uninstall`,
`installed_hook_execution`), Windows Bash proof, cleanup and `live_delivery=not_tested`.
An installed row cannot populate a live/UI target. Every recorded live pass still
needs its required Code checks below. Remaining live Code gaps do not block publication,
but remain untested and must be disclosed. Local WSL live QA cannot certify macOS
or native Linux/Windows live delivery. Desktop Chat/Cowork are experimental stateless
skills; their six rows remain explicit and any pass still needs actual UI QA.
Missing, stale or incomplete required evidence fails the check.

Code receipts bind all four packages and require `clean_install`,
`configured_python`, `automatic_python_upgrade`, `automatic_python_fresh`,
`unconfigured_prompt_delivery`, `prompt_delivery`, `upgrade`, `uninstall`, and
`invalid_python_advisory_then_recovery`. Windows
additionally requires its own `git_bash_absent` or `git_bash_present` proof.
Chat receipts bind only Accuracy and Deterministic Data and require
`clean_install`, `skills_available`, `skill_invocation`, `no_local_hooks`,
`upgrade`, and `uninstall`. Cowork uses the same stateless packages and checks,
with `stateless_boundary` instead of `no_local_hooks`.

Main is the marketplace delivery branch: merging package changes publishes
them before a tag. `scripts/check_marketplace_publication.py --base-ref BASE_SHA`
requires the release evidence on protected PR changes; main and tag builds use
`--release` unconditionally. Only ordinary root README/CONTRIBUTING Markdown,
Markdown under `docs/`, and Python tests under `tests/` are exempt. Package
READMEs, catalogs, receipts, scripts, workflows, unknown paths, symlinks, and
deleted or moved protected source remain guarded. Missing, invalid or
non-ancestor base commits fail closed.

Package hashes cover POSIX relative paths sorted as case-sensitive strings and
exact source bytes, excluding
Python caches. Use a clean LF checkout (`core.autocrlf=false`) for installed
QA, including Windows, so bindings match the published source. Changing a root
guide does not change a package binding; changing its packaged README does.
This guards accidental regressions, not malicious changes by an authorised
maintainer. Checker, receipt and workflow edits require independent review.
Both marketplace catalogs must keep the fixed local package routes and package
identities. Redirected sources, duplicate/unknown packages, inline hook overrides
and changed Codex installation/authentication policy fail; metadata descriptions
may change. Existing package QA cannot certify a new catalog source.

The required combined `release-gates` check includes Linux Python 3.9–3.14,
native Windows Python 3.9/3.14, Git Bash Windows controls, and macOS. The native
gate verifies mandatory hook cases were present and not skipped. Keep that
combined check required in branch protection when editing workflow names.
The native installed-Code matrix installs the pinned CLI, exercises the bundle
lifecycle and directly invokes installed hook registrations with synthetic data.
This checks Accuracy output, Ledger restore and Memory capture/retrieval without
a model call. It proves direct execution, not automatic hook scheduling by Claude.
No CI model credentials or local login copies are used. Standard hosted runners
are [free for public repositories](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Publication overlays exactly four installed receipts from the current `GITHUB_RUN_ID`,
checking the actual tested checkout commit and package bindings. Old schemas,
mixed runs, missing/unknown files and failed cleanup reject. Only fixed fields
are uploaded; paths, raw outputs and profiles stay out of receipts. The overlay
never rewrites committed live outcomes. PR builds test the synthetic merge commit;
main/tag builds rerun on their own checkout. The merge guard checks the PR head.
The local live pass expires when any package byte changes and must be rerun on
an actual logged-in Code host; native offline QA cannot replace it. See
[free QA options](INSTALLED_QA.md#free-local-gaps).

The publication job is also a mandatory dependency: failure, cancellation or
skipping must fail the aggregate. Keep strict, up-to-date branch protection.

## Installed-host QA

Use a clean temporary profile and synthetic prompts/results only. Record the
host version and Python version, source binding and outcome, without raw logs.

1. Install through the marketplace; verify package versions and source bytes.
   Do not use `--plugin-dir` as the installed-plugin test.
2. Leave Python unset and prove discovery on clean installation and upgrade.
   For live QA, prove prompt-hook delivery after upgrading with the option unset.
   Configure an override, reload, and prove delivery in a fresh session.
   Exercise a path containing spaces/apostrophes/Unicode. Check an invalid
   executable is advisory; restore configuration and prove delivery again.
3. Upgrade from the previous package and verify versions, registrations and
   saved options. Record any required new configuration step.
4. Uninstall and verify registration removal.
5. Repeat native Windows without Git Bash, Windows with Git Bash, Linux/WSL
   and macOS. For Desktop, record **Chat**, **Code** or **Cowork** separately;
   a Chat skills test cannot certify a Cowork hook. Confirm Chat never claims
   it captured or retrieved local memory. Leave unavailable targets untested.

Use the host-specific check names above for Desktop skills QA. Code checks
cannot substitute for a Desktop receipt. Synthetic persistence tests separately
cover capture cutoff, pause/clear boundaries, exactly-once writes and expiry.
Claims about live installed capture or default deletion versus `--keep-data`
retention require separate installed-session QA; registration checks alone do
not establish them.

Official host contracts: [exec hooks](https://code.claude.com/docs/en/hooks),
[plugin configuration](https://code.claude.com/docs/en/plugins-reference),
and [plugins in Claude](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).
Linux Desktop beta provides Chat/Cowork/Code on supported Ubuntu/Debian hosts;
Cowork additionally needs working virtualisation. Its plugin UI remains
unverified here. [Linux Desktop requirements](https://code.claude.com/docs/en/desktop-linux)
were checked on 3 Oct 2026; beta behavior can change.

## Evidence Memory contention

Overlapping ordinary hooks defer quietly when the session lock is busy. They
leave the cursor untouched; the next capture or explicit `sync TRANSCRIPT_PATH`
retries the same source. Restore, Stop and PreCompact wait at most 0.5 seconds
for the lock, then emit a fixed advisory if still busy. A final deferred capture
may need explicit sync; a restore that remains busy cannot inject its packet.
`status`/`sync` report `memory_session_lock_busy` (including read-only status).
Persistent failures inside capture still emit diagnostics. Never delete a lock
file to bypass contention: a file's existence does not mean its lock is held.
