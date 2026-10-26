# Preview validation and limits

Config Doctor 0.1.3 is a standalone source-audit workflow for Python 3.11+.
It uses the standard library and your existing agent for semantic review.

From this folder, run the existing contract checks:

```text
python -B workflow_tests.py
python -B tests.py
```

The 14 workflow tests cover real packet preparation and report rendering,
source identity/freshness, review coverage, exact edit spans, unsupported input
and credential-pattern refusal, inert hook/plugin source, structural settings
summaries and delivery of the complete current audit prompt. The six scanner
tests check bounded lexical leads, negation, explicit input handling and the
read-only CLI boundary. Test child processes are hidden on Windows.

These are synthetic contract checks, not a live model accuracy benchmark or a
general security certification. A quiet scanner is not a semantic pass. The
scanner's proposed wording is a hypothesis for review; its public catalogue cites
the bundled principles rather than unpublished study results.

Release qualification runs these checks from an extracted ZIP on native Windows,
checks bundled Markdown links and compares the archive with committed source.
The existing repository CI runs the Doctor checks on Python 3.11 on Linux.
See the [release](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.3)
for completed results. macOS execution, other host surfaces and comparative model
benefit remain unverified for this preview.

Prepared packets contain full selected text sources. Keep them and reports
private. Structural settings summaries intentionally omit commands, URLs and
environment values, so they cannot prove the full live configuration. Credential
patterns are a backstop; instructions are not a filesystem sandbox. Prior context
already loaded by the host cannot be removed by the startup prompt.

The LLM Accuracy plugin's installation receipts do not qualify this separate
tool, and Config Doctor's tests do not establish that a plugin is loaded or used.
Applying recommended changes remains a separate user decision.
