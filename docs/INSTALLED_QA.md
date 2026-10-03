# Installed-host QA handoff

Code publication requires all four native installation targets plus at least
one genuine current-source local live Code pass. Live coverage on other hosts
stays explicitly untested. Offline execution does not certify model-driven
Claude scheduling or Desktop UI. Desktop Chat/Cowork remain experimental
stateless skills; keep their six untested rows visible.

## Hosted Code QA

The required `installed-code` matrix uses actual Linux/macOS/Windows VMs with
and without Git Bash. Standard runners are [free for public repositories](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).
Claude 2.1.287 is pinned: official manifest and binary must match committed
checksums. Updating pins needs independent review. A clean LF checkout and
`v0.6.5` baseline prove installation, configured Python, upgrade and uninstall.

The free installed-hook probe directly executes installed argument vectors:
Accuracy emits its reminder, Ledger persists/restores a synthetic compact
summary, and Memory captures/retrieves a synthetic tool result exactly once.
This is direct execution with simulated host input, not live Claude scheduling.
The probe uses temporary data and profiles, never personal persisted sessions.
All five checks and cleanup must succeed; Windows also proves actual Bash
presence/absence. No hosted job copies a login, receives a model secret or calls
a model. Optional `--live` remains available for dedicated manual testing.

Upload only successful fixed-field installation receipts for seven days.
Temporary profiles, paths, raw outputs, prompts, answers and credentials are
never uploaded. Publication requires exactly four artifacts tied to the current
GitHub run ID, actual checkout SHA, matching OS/mode and package bytes/versions.
PR receipts bind the synthetic merge commit; main reruns after merge. These are
reviewed maintainer attestations, not tamper-resistant certificates.
Live Code receipts remain separate. At least one local live pass must match the
current package bytes; no historical receipt is rehashed to clear the gate.

The no-Bash scenario removes Bash only on disposable hosted Windows, retains
Git and selects PowerShell. PATH and known Git roots are probed for remaining
usable Bash. Never remove or rename Bash on your own workstation for QA.

## Free local gaps

- **Local live Code:** use the existing Claude subscription login in an isolated
  temporary profile and the terminal harness below. No extra API credential is
  required. WSL and native Windows are separate targets. Recheck source bindings
  after every package change.
- **Installed persistence:** the native direct-hook probe provides free capture,
  retrieval, exactly-once ingestion and Ledger restore checks on all four native jobs. Live
  Memory/Ledger model-driven capture and uninstall data retention remain separate.
- **Windows PowerShell mode:** set the child `CLAUDE_CODE_USE_POWERSHELL_TOOL=1`
  and run the local harness. If Bash is installed, label this supplemental proof
  as PowerShell mode with Bash present; it cannot certify Bash absence. The free
  hosted Windows no-Bash job supplies actual absence coverage for offline checks.
  A [current Memory 0.5.0 native Windows receipt](validation/platform-windows-powershell-bundle-memory-0.5.0.json)
  passes live Accuracy delivery/recovery and direct synthetic installed persistence
  with that flag requested. Its no-tool sessions do not exercise the PowerShell tool.
  The [earlier Memory 0.4.0 receipt](validation/historical-platform-windows-powershell-bundle-memory-0.4.0.json)
  is historical and does not certify the current Memory package. Current local WSL
  delivery is recorded [separately](validation/platform-wsl-bundle-memory-0.5.0.json).
  An [ordinary native Windows run](validation/platform-windows-bundle-memory-0.5.0.json)
  separately proves the candidate's Bash-present live row without requesting
  PowerShell mode. Neither terminal run certifies shell-tool execution or Desktop UI.
- **Desktop UI:** stateless packaging/source checks and CLI skill discovery are
  useful screens; only the real app can certify Chat/Cowork/UI. Use a fresh
  synthetic context and the UI battery below. Keep actual UI gaps untested if no
  isolated app context is available; do not modify a personal conversation/profile.
- **macOS:** the native hosted job provides free installation/runtime checks.
  Live macOS/desktop delivery requires an actual available Mac and local login;
  WSL, containers and Python platform mocks do not reproduce it.
- **VM options:** Windows Sandbox is a free disposable option on eligible Windows
  editions, but [installation may require an admin change and reboot](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-install).
  Do not enable OS features or install virtualization tooling just to manufacture
  a receipt. Use existing tools or the free hosted native jobs first.

## Code terminal QA

Use a clean checkout of the candidate, with Git `core.autocrlf=false` before
checkout on Windows. Install Claude Code 2.1.287+ and a working Python 3.9+.
Use the host's own executable: Linux Python on WSL, Windows Python on native
Windows. Log in locally; never copy credentials to CI or submit them in a receipt.

Run this on each actual host, using an available ancestor whose package bytes
differ from the candidate as the baseline:

```text
python scripts/claude_bundle_smoke.py --baseline origin/main --receipt bundle-smoke.json
python scripts/claude_install_smoke.py --receipt accuracy-smoke.json
```

On Linux/WSL/macOS, use the verified `python3` command if needed. The bundle
harness uses a temporary local marketplace path containing spaces, an apostrophe
and Unicode. It checks versions and full package bytes for all four packages,
upgrade, new Python configuration, saved-option preservation on refresh,
clean install, Accuracy prompt delivery and removal of all four registrations.
It also proves an unavailable Python option leaves the turn running, then
restores configuration and confirms hook delivery in a fresh session.
It leaves the real profile's configuration alone; authentication is copied only
to a temporary profile. It emits fixed checks and hashes, never raw answers,
settings, credentials or hook payloads. A setup/model failure is a failed smoke;
`--skip-live` is partial and exits 2, never publication proof.

The second harness checks installed/default, bypass and release-archive Accuracy
delivery on committed source. Neither harness certifies live Ledger/Memory
capture, uninstall data retention, Desktop UI, or Windows Bash availability.
The direct installed-hook probe checks synthetic persistence separately; actual
model-driven capture, data retention, UI and Bash proof need their own evidence. The marketplace source is local, not a fresh hosted
GitHub download.

Before recording a Code pass, confirm the invalid-Python recovery field passes
alongside every other required Code check. Review the raw-free receipts locally, then record
the bundle receipt on the matching target:

```text
python scripts/record_compatibility_pass.py --target code-wsl --bundle-receipt bundle-smoke.json
```

The recorder accepts only a passing, non-partial, cleaned-up live receipt from
that platform. It copies the host version, Python version, package bindings and
required checks, seals the row to the receipt's `source_commit`, and writes
nothing if the candidate would then fail the checker. Do not edit old receipt
hashes or seals.

Native Windows requires two distinct runs: without accessible Git Bash and with
Git Bash available. Inspect the effective child PATH and executable resolution
for each run. Record `git_bash_absent` or `git_bash_present` only after proving
that environment, alongside the required Code checks: pass `--git-bash absent` or
`--git-bash present` to the recorder for that run. WSL is a separate target and
does not certify either Windows scenario. Native Linux is also separate from WSL.

## Desktop skills QA

Use the actual Windows/macOS/Linux beta Desktop application and a fresh test context. Test
Chat and Cowork separately, with only Accuracy and Deterministic Data:

1. Install the candidate stateless packages and verify their source/version.
2. Confirm each package's skills are available; invoke each with synthetic data.
3. In Chat, confirm skills do not claim local hooks, doctor or memory capture.
   In Cowork, confirm the stateless boundary and absence of Ledger/Memory claims.
4. Upgrade from the previous packages, then verify the candidate skills again.
5. Remove both packages and confirm their registrations/skills are gone.

Write the result as a row file with `outcome` `pass`, the target's `platform`
and `host_kind`, the actual app version as `host_version`, the two package
bindings as `packages`, the exact
[host-specific checks](COMPATIBILITY.md#release-guardrails) as `checks`, and the
full commit you installed from as `source_commit`. Then seal it with
`python scripts/record_compatibility_pass.py --target <target> --row row.json`.
Add no other field: stateless UI QA has no `python_version`, and the checker
refuses a pass row with any field it does not record. Code-only checks cannot certify these targets.
Desktop Code UI and Cowork hook execution remain explicitly unverified even
after these stateless checks pass.

Linux beta needs its supported Ubuntu/Debian desktop environment; Cowork also
needs working KVM/QEMU virtualisation. Follow the
[official Linux Desktop requirements](https://code.claude.com/docs/en/desktop-linux).
WSL terminal QA cannot substitute for this Desktop UI.

## Review the publication decision

```text
python scripts/check_compatibility.py
python scripts/check_compatibility.py --release
python scripts/check_marketplace_publication.py --base-ref ACTUAL_PR_BASE_SHA
```

All four current-source native installation rows and at least one live Code
pass must be verified before publication and the required aggregate can succeed.
Locally reproducing CI overlays also requires `GITHUB_RUN_ID` from the actual run.
Checker/workflow/receipt edits need independent review. The receipts guard
accidental omissions; they are maintainer attestations, not tamper-resistant
certificates. Do not bypass the gate to publish an incomplete candidate.
