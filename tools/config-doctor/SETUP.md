# A simple setup for data and finance work


Use short reviewed global instructions, a project brief containing agreed metric
definitions and source locations, read-only data access where possible, and
executable checks for consequential results. Add one independent review for
material conclusions or production changes. Start with the
[LLM Accuracy plugin](https://github.com/warwick-bit/llm-accuracy) if you want
advisory reminders; keep extra integrations off until a concrete need justifies
them. These are practitioner recommendations, not a proven combined accuracy gain.

### Four checks that make the result easier to trust

| Check | What to do in practice |
| --- | --- |
| Missing data is not zero | If March's billing file is missing, call March unavailable. If complete March coverage shows no eligible activity, zero may be correct. Finish the independently supported parts and label any partial total. |
| Give the reviewer the evidence | Supply the original question, agreed definitions, relevant source data, calculation and proposed conclusion. Ask the reviewer to check the calculation and side claims against those sources. Resolve disagreements using evidence; two models agreeing is not verification. |
| Explain what a passing checker checked | State whether it checks arithmetic, source reconciliation, report labels or something else. Rebuilding a report does not by itself verify its meaning. For a label/value check, use a swapped-label example it must reject and a correctly reordered example it must accept when that risk matters. |
| Keep prediction tuning separate from final evaluation | Choose models and thresholds using training/validation data, then evaluate on an untouched holdout suitable for the intended use. If you use the final results to choose again, disclose that they became selection evidence; they no longer provide an independent final estimate. |

These are practitioner recommendations, not evidence that every failure is prevented.

### What to do about memory

For consequential data and finance work, our conservative starting recommendation
is **automatic memory off, reviewed instructions and a small project brief on**.
The tradeoff is having to supply relevant context again. We have not established
that memory-off is universally more accurate. It removes one route for unnoticed
carryover; it does not remove earlier messages, project files or errors preserved
in a long session's summary.

| Kind of context | Practical default |
| --- | --- |
| Stable preferences and working rules | Keep a short, reviewed instruction file: language, formatting, tools and permissions. |
| Metric definitions and current project decisions | Keep them in the existing project brief with source/version, cutoff and unresolved assumptions. Review changes before relying on them. |
| Historical findings and calculations | Retain dated evidence and reproducible code. Reuse only when the source, definition and freshness still fit the new question. |
| Automatically saved notes and recalled chats | Start disabled for consequential analysis. Retrieve prior material deliberately when needed; treat it as a lead, not current evidence. |
| The current conversation and compaction summary | Still require checks. On resume, read the brief and relevant sources, reconcile corrections and identify unresolved decisions. |

For example, "use Australian English" is a useful durable preference. "Churn is
4.2%" needs its period, population, definition and source; it must not silently
become this month's answer. A remembered explanation such as "the pipeline is
fixed" needs fresh evidence when the affected source or environment changes.

A short global instruction can make that boundary explicit:

```text
Treat remembered claims and previous answers as leads, not current evidence.
Reuse a result only when its source, scope and freshness still fit the question.
Keep agreed definitions and decisions in the existing project brief. Preserve
dated evidence, and visibly correct superseded conclusions and dependent outputs.
Do not save new persistent memories unless I ask. State what remains unknown.
```

That instruction is advisory; use the host's settings to control automatic memory.
In Claude Code, use `/memory` to manage auto memory; `autoMemoryEnabled: false`
is the documented project setting. In Claude chat, memory and past-chat search
have separate controls. Check both when the aim is a fresh audit. Disabling auto
memory does not disable reviewed instruction files or additional memory plugins.
Host behavior varies; do not infer a setting from a missing key or assume one
toggle covers every host. No personal setting is changed by this guide.

Current controls, checked 26 October 2026:
https://code.claude.com/docs/en/memory and
https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context.

Doctor should check the selected memory sources, their authority and correction
rules. "Memory disabled" alone is not a clean bill of health. Use Doctor after
setup or a material configuration change, not as a compulsory step on every task.

### Choose a data-access route you can inspect and repeat

Prefer native SQL, an official API/SDK or an established CLI for repeatable data
work when it meets the task and access requirements. Reuse the approved route;
do not build a custom integration just to avoid MCP. This is an engineering
preference, not a measured finding that one transport produces truer answers.

| Route | Useful when |
| --- | --- |
| SQL or a database client | You need explicit joins, filters, populations and server-side aggregates. |
| Official API/SDK or CLI | You need repeatable requests, bulk exports or a saved analysis script with structured results. |
| An approved MCP connector | It supplies the necessary operations, scoped access, metadata and inspectable results without extra integration work. |

MCP can expose the same API and return structured data. Judge the actual connector,
not its name. For every route, check pagination, row limits/truncation, filters,
timezones, snapshot/coverage and errors before treating a result as complete.
Save the query or request parameters and relevant output under the task's data
handling rules; keep credentials out of artifacts. Process large data in the
database or code and bring bounded results into the conversation. A successful
exit or HTTP response alone does not establish correct or complete data.

Use read-only credentials where possible. A preferred CLI/API is not permission
to bypass an approved connector, widen access or retry a refused production write.
Keep unused integrations off. Claude Code's official guidance covers both
[CLI tools](https://code.claude.com/docs/en/best-practices#use-cli-tools) and
[MCP connections](https://code.claude.com/docs/en/mcp).
