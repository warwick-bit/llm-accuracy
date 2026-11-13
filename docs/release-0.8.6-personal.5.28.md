# LLM Accuracy 0.8.6-personal.5.28

_Prepared 13 Nov 2026 for the marketplace change in [PR #94](https://github.com/warwick-bit/llm-accuracy/pull/94). GitHub tagging and ZIP publication are separate steps._

## Changes

- Verify supports opt-in `--places shown`: one call can check `1/3=0.33` at 2 decimal places and `1/8=0.125` at 3. Numeric `--places N` still uses one precision throughout the call; omitting it still compares exactly.
- Precision comes from the stated right-hand side, including percentage units. Fractions, exponent notation and numbers showing more than 12 decimal places are compared exactly. Each computed check records its decimal places, or `null` for exact comparison.
- At an exact tie, shown mode accepts half-even or half-up away from zero. A half-up-only match records `tie_pass: half_up`. Other comparisons keep their existing behavior.
- Both CLI help commands work after escaping percent signs for argparse. Verify's instructions describe the new mode and its boundaries.
- Earlier background-delivery changes remain documented in the [0.8.6-personal.5.27 release notes](release-0.8.6-personal.5.27.md).

## Qualification and limits

- 35 new CLI cases cover mixed precisions, legacy modes, signed ties, percentage precision, exact fallbacks, bounds and both help paths. Restoring the original checker in a disposable tree reproduces its shown-argument rejection and help-format errors.
- Clean native Windows full suites passed: Python 3.13/PowerShell **1,446 passed, 32 skipped**; Python 3.9.25/Git Bash **1,452 passed, 26 skipped**. Platform-dependent skips remain coverage limits.
- Pinned Ruff 0.15.2 lint, manifest parsing, hook compilation, distribution boundaries and compatibility validation pass. Receipt/compatibility/publication regression checks report **134 passed**.
- The [native Windows live bundle receipt](validation/claude-bundle-smoke-0.8.6-personal.5.28.json) records clean installation, configuration, upgrade, automatic Python discovery, direct installed-hook execution, live Accuracy delivery, invalid-Python recovery, uninstall and cleanup. Git Bash was present; this is not Bash-absence or other-OS live evidence.
- The [Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.6-personal.5.28.json) records 65 tracked files with **0 installed-byte mismatches**, expected hook delivery in installed and archive sessions, and cleanup. Footer presentation is observed separately and is not a passing requirement of this smoke.
- Both live receipts bind tested source `1c8a7d0363b81668fbe53b7662c54e762ed39fa1` and the candidate package bytes, using Claude Code 2.1.287 and native Python 3.13.1. They use isolated local-path installations and do not certify a hosted download, the owner's active sessions, Desktop UI, factual accuracy or an adherence rate.
- Four native installed-host CI targets and the required publication aggregate must pass on the final PR head before merge. Linux/macOS/Windows installation evidence does not replace a live receipt; other live/UI targets remain explicitly untested.
