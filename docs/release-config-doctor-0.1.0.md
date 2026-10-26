# Config Doctor 0.1.0 preview

A standalone workflow for reviewing selected Claude Code or Codex instructions,
settings summaries, plugin guidance and MCP tool descriptions. It identifies
conflicting rules, stale assumptions and source-coverage gaps, then validates
the agent's assessment and proposed edit spans. It does not apply changes.

Open a fresh local Claude Code or Codex session and paste the prompt from the
[guide](../tools/config-doctor/README.md). Your agent fetches the released tool;
no manual download is needed. The [preview ZIP](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.0)
remains available for manual setup. Python 3.11+ is required; no extra Python
packages or separate API key are needed. Your agent performs the review.

The download includes the workflow, scanner, self-contained guidance, synthetic
examples, existing contract tests and MIT licence. It includes no private eval
reports, customer data, audit packets or user configuration. Scanner leads and
proposed replacements are hypotheses, not published evidence of effectiveness.

This is separate from the plugin's Accuracy Doctor diagnostic. It does not
change any plugin package or version, install hooks or enable integrations.
LLM Accuracy 0.8.2 remains the Latest plugin release; this preview has its own
`config-doctor-v0.1.0` tag and ZIP/checksum.

Qualification checks use the extracted standalone package on native Windows and
the existing 20 workflow/scanner contracts. Repository CI also runs those checks
on Python 3.11 on Linux. See the published release for completed results and the
exact merge commit. macOS execution and comparative model benefit remain
unverified. A source audit does not prove runtime loading or correct answers.
