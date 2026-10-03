# Installed-host QA handoff

Code publication stays on hold until all five required Code targets in
[the current candidate](validation/compatibility-candidate.json) passes. CI
Python tests prove runtime behavior; they do not prove installed Claude delivery.
Never replace missing machine or UI evidence with a synthetic pass.
Desktop Chat/Cowork are experimental stateless skills. Keep their six untested
rows visible; those gaps do not block Code publication. A recorded experimental
pass still requires actual host-specific QA.

## Hosted Code QA

The required `installed-code` matrix uses actual GitHub Linux/macOS/Windows VMs.
It downloads Claude 2.1.287 using committed checksums; both the official manifest
and binary must match. Updating the pin needs independent review. It checks the
bundle against the fixed `v0.6.5` upgrade baseline in a clean LF checkout.
Installation-only checks run without credentials and remain explicitly partial.
Live checks require exactly one dedicated secret: `CLAUDE_CODE_OAUTH_TOKEN` or
`ANTHROPIC_API_KEY`. Missing/both credentials fail with a fixed diagnostic.

Configure the dedicated credential through GitHub Actions secrets UI, preferably
with an approved environment/branch restriction; never paste it into chat, logs,
source, or a receipt. Current workflow uses repository secrets; same-repository
workflow editors are trusted and can access them. Review workflow changes before
running with credentials. Fork PRs receive no secrets and cannot pass the live
gate; a maintainer must review and test an exact candidate on a trusted branch.
Do not copy your local login file into CI. API authentication bills the API
account; OAuth uses its associated account. The smoke runs two bounded no-tool
turns per native target, each with a $1 maximum budget and finite timeout.

Only successful fixed-field live receipts are uploaded, retained for seven days.
Temporary profiles, raw outputs, prompts, answers and credentials are never
uploaded. Publication checks all four native receipt filenames, source commit,
OS/mode, versions, source bindings and six Code checks plus each Windows Bash
proof. PR receipts bind the tested synthetic merge checkout; main reruns QA after
merge. Receipts are attestations from reviewed workflow code, not tamper-resistant
proof against a maintainer. WSL remains separately tested on actual WSL and its
committed receipt must be regenerated when package bytes change.

The no-Bash scenario removes Bash executables only on disposable hosted Windows,
retains Git, clears its PATH/override and enables native PowerShell. The checker
probes PATH and known Git roots to reject remaining usable Bash. Never perform
that removal on your own machine. A host failure keeps the target unverified;
do not weaken the receipt definition to clear it.

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
Those need their own tests. The marketplace source is local, not a fresh hosted
GitHub download.

Before recording a Code pass, confirm the invalid-Python recovery field passes
alongside all six Code checks. Review the raw-free receipts locally. Transfer only the
actual version, platform and host mode, current package bindings and required true checks into the
matching candidate target; do not edit old receipt hashes.

Native Windows requires two distinct runs: without accessible Git Bash and with
Git Bash available. Inspect the effective child PATH and executable resolution
for each run. Record `git_bash_absent` or `git_bash_present` only after proving
that environment, alongside the six Code checks. WSL is a separate target and
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

Record the actual app version, the two package bindings and the exact
[host-specific checks](COMPATIBILITY.md#release-guardrails). No Python version
is required for stateless UI QA. Code-only checks cannot certify these targets.
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

Only a current-source installed pass counts. All five required Code targets must pass
before the marketplace publication job and required aggregate can succeed.
Checker/workflow/receipt edits need independent review. The receipts guard
accidental omissions; they are maintainer attestations, not tamper-resistant
certificates. Do not bypass the gate to publish an incomplete candidate.
