# Evidence Memory 0.3.0

Evidence Memory now stores **external results** by default: MCP tool calls,
`WebFetch` and `WebSearch`, and Codex cells that call an MCP or web tool. Local
shell, file and edit output is no longer stored. In a replay of the maintainer's
own sessions, external calls were about 4-7% of tool calls and 11-19% of result
bytes; the earlier capture-everything indexes recorded no organic retrieval.

**Restricted tools are withheld.** MCP tools whose names contain words such as
`payroll`, `employee`, `bank`, `tax`, `passport` or `secret` are never stored,
in any mode. This is best effort: a general tool with an innocuous name can
still return sensitive rows. Add words, or restore the 0.2 capture-everything
behaviour, with `${CLAUDE_PLUGIN_DATA}/config.json`; see the
[plugin guide](../plugins/evidence-memory/README.md#what-is-captured).

**The post-compaction packet now points at results.** It lists up to ten recent
paired external results as short IDs with tool name, time, size and error flag,
plus a resolved CLI command prefix. It carries no call arguments or result
content, and it is omitted when there is nothing to retrieve. `fetch` accepts a
unique 12-character ID prefix. In a synthetic comparison the new packet kept
exact recovery at 3/3 while cutting mean turns from 5.0 to 3.7, and the command
prefix alone recovered 3/3 without the skill, against 0/3 for the old packet.
See the [validation receipt](validation/evidence-memory-0.3.0-2026-09-30.json)
for its limits; live long-session benefit remains unmeasured.

**Existing indexes** keep their earlier unscoped rows until you run
`/evidence-memory:memory clear`; `status` reports them as
`capture_policy: legacy_unscoped_rows`. New rows follow the new scope.

**Read actions work in read-only sandboxes.** `status`, `lookup`, `search`,
`fetch` and `state` fall back to a read-only open when the data directory
cannot be written, as in Codex's sandbox or a sandboxed shell; they then record
no retrieval counts.

**Codex (experimental).** Evidence Memory also installs as a Codex plugin with
the same hook commands (`codex plugin add evidence-memory@llm-accuracy`). In
Codex, installing enables capture, the stored unit is a whole code-mode cell's
printed output, and the skill uses a Codex-specific command because Codex
does not fill in its placeholders; see the
[plugin guide](../plugins/evidence-memory/README.md#codex-experimental).

To update, run `claude plugin marketplace update llm-accuracy` and
`claude plugin update evidence-memory@llm-accuracy`, then restart Claude Code or
run `/reload-plugins`.
