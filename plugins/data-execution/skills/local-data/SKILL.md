---
name: local-data
description: Explicitly capture a completed local JSON or CSV tool export, calculate exact grouped totals, or retrieve selected records from an existing Data Execution snapshot.
disable-model-invocation: true
argument-hint: "[capture, calculate, retrieve or purge; adapter/export path or snapshot ID]"
---

# Local Data Execution

Read `${CLAUDE_PLUGIN_ROOT}/README.md` before first use. This is an experimental
POSIX local-storage workflow, not a native MCP interceptor. Do not install or
configure provider integrations as part of this skill.

1. Confirm the user's authorized source, scope and private storage location.
   Disclose that a full local copy is kept for 30 days by default, configurable
   with `--retention-days`. Expiry blocks reads; physical cleanup runs on capture
   or explicit `purge`, not continuously. Prior authorization persists.
2. Use a user-owned, reviewed JSON adapter. It must identify source/account/mode,
   period/timezone, filters, grain, unit, metric definition and completeness basis.
   Do not invent mappings, claim an example is production-ready, or mark a partial
   source complete. Group monetary sums by currency. Routing/definition ambiguity
   remains the user's catalogue's responsibility.
3. Prefer direct detail for small inputs or tasks needing most fields. For large
   aggregation/follow-up tasks, capture from a successful read-only export before
   its raw content enters model context. Follow the staged shell pattern in the
   README; never use raw data in command arguments, heredocs or chat. Native MCP
   responses already delivered to Claude do not save initial context by copying
   them afterwards. If no source-side export exists, explain that limitation.
4. Invoke `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/local_data.py"` with `--store`
   before the subcommand if selecting a custom directory. Capture requires
   `--adapter PATH --input PATH`; optional `--retention-days N`. Read only its
   receipt. Keep the returned snapshot ID, scope, location and expiry available
   for follow-ups. Storage alone does not preserve conversation references.
5. Use `sum SNAPSHOT --scope SCOPE` for all groups in a single calculation.
   Request only necessary detail with `detail SNAPSHOT --scope SCOPE --id ID
   --field FIELD`; IDs and fields can repeat as flags. Amounts and detail numbers
   are strings for exact transport. Do not round, cast through binary float, mix
   currencies or reinterpret minor units.
6. Preserve errors and all receipt qualifications. Partial source totals are
   withheld even if its available detail can be retrieved. Completeness assertions
   do not establish atomicity, freshness or truth. Never reconstruct withheld
   totals from partial details or substitute a new snapshot silently.
7. Report the requested result, unit/currency, scope, row count, completeness,
   capture time, atomicity caveat and snapshot reference. A snapshot ID is a local
   reference, not a provider link or independent evidence certification. Use the
   existing evidence-receipt schema separately if another workflow requires it.
   Respect an explicitly requested machine-readable output format. For JSON-only
   requests, return the requested JSON object without a preamble, trailing prose
   or Markdown fence. Preserve material qualifications in the requested fields;
   if the schema cannot express a necessary qualification, report that limitation
   rather than silently dropping it.
8. `purge` deletes expired snapshots only; `delete SNAPSHOT` removes a specified
   snapshot. Never delete unrelated files or change global Claude retention.
