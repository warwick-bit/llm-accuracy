# Accuracy 0.8.3

This release adds optional source-verification tools and failed-refresh checks:

- CSV input with explicit column/unit/population mappings and source-row lineage.
- Old/current source rechecks retaining both results for every original claim.
- Local citation and quotation checks, separate from semantic claim support.
- A final-report assertion inventory showing unlisted lines, rewritten assertions
  and changed source files behind manual assessments.
- Declared input/output snapshots and failed-refresh checks that detect overwritten
  or deleted required outputs without running or repairing a producer.

Accuracy and Deterministic Data receipt validators reject duplicate JSON keys and
return structured errors for decoder limits. The companion Deterministic Data
package is version 0.1.2; its declared catalogue/routing scope is unchanged.

These are bounded verification capabilities. Exact source definitions remain
supplied assumptions; quote presence is not entailment; line coverage is not
semantic completeness; observed file preservation does not guarantee atomicity,
crash durability or content correctness. No general model-accuracy improvement
has been measured for these additions. See the [source/eval evidence mapping](source-verification-evidence.md).

Fresh qualification used native Windows with Git Bash, Python 3.13.1 and pinned
Claude Code 2.1.287. The [bundle receipt](validation/claude-bundle-smoke-0.8.3.json)
records installation, upgrade, live Accuracy delivery, invalid-Python recovery,
uninstall and isolated cleanup. The [installation/archive receipt](validation/claude-code-smoke-0.8.3.json)
records exact installed-file matching and bounded live sessions. The live row in
the [compatibility candidate](validation/compatibility-candidate.json) was generated
by the owned recorder for the actual tested source commit. Normal user configuration
was not changed by these isolated checks.

Publication requires all four fresh native installed CI targets (Linux, macOS,
Windows with and without Bash), the marketplace publication check and the required
release-gates aggregate. Hosted installed checks directly execute hooks; they do
not certify live model delivery on other hosts. Desktop Chat/Code UI, Cowork and
general model efficacy remain unverified.

The [published release](https://github.com/warwick-bit/llm-accuracy/releases/tag/v0.8.3)
will identify the final marketplace merge commit and provide ZIPs and checksums.
