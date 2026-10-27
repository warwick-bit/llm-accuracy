# Config Doctor 0.1.1 preview

Audit recommendations now explain what to do first, what is already covered,
what needs more evidence and what is optional. The saved report and chat summary
include reasons, finding or coverage IDs, and up to three immediate next actions.
An urgent evidence check can precede a proposed edit. Users still choose what
to apply; priority does not grant approval.

Start with the [guide](../tools/config-doctor/README.md). Its copyable prompt lets
your local Claude Code or Codex session fetch the tool. Python 3.11+ is required.
The [0.1.1 preview](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.1)
has its own ZIP and checksum. Existing 0.1.0 assets remain unchanged.

This updates audit guidance using the existing assessment summary and finding
fields. No schema, scoring system, dependencies or plugin packages change.
Qualification uses the existing 20 workflow/scanner checks, extracted archive
parity and link checks, plus repository CI and independent review. See the
published release for completed results. These check delivery and report
consistency; they do not establish model benefit or reliable prioritisation in
every audit. macOS execution remains unverified.
