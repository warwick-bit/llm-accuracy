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

The initial independent source review found no blocking defects. Release
qualification and final-head CI are pending. Fresh local live installation and
archive receipts must be recorded before merge; historical receipts do not certify
this source. Other live hosts and Desktop/Cowork UI remain untested. Reminder
delivery and passing tests do not prove model compliance or improved accuracy.
