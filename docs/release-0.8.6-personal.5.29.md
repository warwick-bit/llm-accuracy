# LLM Accuracy 0.8.6-personal.5.29

Prepared for the marketplace change in [PR #95](https://github.com/warwick-bit/llm-accuracy/pull/95).
GitHub tagging and hosted ZIP publication are separate steps.

## Changes

- Verify applies checks while working and to the actual draft before delivery.
  Loading the skill is no longer required to be the first action, and loading it
  early does not count as checking the final answer.
- Reuse an observed executed calculation when its inputs and source version
  match the requested calculation. Still check definitions, units and faithful
  transcription; recalculate after changed inputs, transformations, newly
  introduced rounding or discrepancies.
- Final source rereading, clarification and saved-file inspection remain required.
  The mixed-precision calculator is unchanged from
  [0.8.6-personal.5.28](release-0.8.6-personal.5.28.md).
- Keep the Python 3.9 CI leg on Ubuntu 24.04 after setup failed on Ubuntu 26.04;
  preserve all other test and publication requirements. The
  [official Python build manifest](https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json)
  lists the supported Ubuntu 24.04 build.

## Qualification and limits

The initial native Windows suite reported 1,445 passed, 32 skipped and one
archive failure because the builder rejects uncommitted source. After committing
the unchanged package, the archive group passed with 9 passed and 1 skipped.
The focused hook checks passed all 28 cases; the updated assertions failed in
18 intended cases against the original hook. Ruff, manifest parsing, hook
compilation, distribution boundaries and source-binding checks passed.

The initial independent source review found no blocking defects. After the
selected Personal login was refreshed, the [native Windows live bundle
receipt](validation/claude-bundle-smoke-0.8.6-personal.5.29.json) passed clean
installation, configuration, upgrade, automatic Python discovery, installed-hook
execution, live delivery, invalid-Python recovery, uninstall and cleanup.
The [installation/archive receipt](validation/claude-code-smoke-0.8.6-personal.5.29.json)
also passed, with 65 tracked files and 0 installed-byte mismatches, expected hook
delivery in installed and archive sessions, and cleanup. Footer layout is
observed separately and is not a passing requirement of this smoke.

Both receipts bind tested source `eb1015a13f05f6bddf147988b6fe2a5a5cf95d50`,
using Claude Code 2.1.287 and native Python 3.13.1. The existing recorder sealed
the actual bundle pass into the Windows-with-Git-Bash live row. The package bytes
remain unchanged after that tested commit. Final-head CI, all four native
installation targets and publication validation must pass before merge.

This local-path Windows qualification does not certify a hosted download,
Windows without Git Bash, other live hosts, the owner's active sessions or
Desktop/Cowork UI. Reminder delivery and passing tests do not prove model
compliance or improved accuracy. Historical receipts do not certify this source.

The follow-up native qualification regression group passed with 191 passed and
1 skipped. The initial fresh bundle attempt passed installation and direct hook checks,
but model delivery failed; an isolated no-plugin request identified expired
OAuth authentication. That failed attempt remains historical and was superseded
by the successful fresh runs above after login refresh.

The final receipt/compatibility/CI-installation/publication regression group
passed all 171 cases. The bounded independent evidence review returned PASS
with no findings, resolving the earlier live-qualification blocker while
retaining final-head CI and publication as mandatory merge conditions.
