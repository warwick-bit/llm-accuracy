# Config Doctor 0.1.2 preview

Findings and questions now use plain English: what was found, why it matters,
how certain it is and the simplest next step. Exact evidence and proposed edits
remain available in the supporting report, with a plain-English explanation.

After the prioritised report, Doctor offers a useful follow-up through the
client's interactive multiple-choice question tool: **Check what's uncertain**,
**Try a change safely**, or **Finish here**. It explains what each check would
tell you, which files or tools it needs and the likely effort. Inapplicable choices
are omitted; no useful follow-up means no extra question. When the tool is
unavailable in the current mode, the agent presents the choices in chat.

The selection covers only the described scope. New evidence updates the affected
findings and priorities; applying edits remains separate. JSON-only batch audits
are unchanged. This is guidance in the existing workflow, with no new runtime,
schema, dependencies or test framework.

Use the [startup guide](../tools/config-doctor/README.md) or the
[0.1.2 preview release](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.2).
The agent fetches the released ZIP; Python 3.11+ is required. Prior release assets
and plugin packages remain unchanged.

Qualification uses the existing 20 Doctor contract checks, archive/source parity,
bundled link checks, independent review and required repository CI. See the
published release for completed results. Prompt delivery does not establish
successful question-tool use in every client/mode or measured model benefit.
