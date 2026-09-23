# Data Execution — experimental POSIX pilot

Save a tool's complete output locally, calculate over that snapshot, and return
compact receipts or selected detail to Claude. This can reduce repeated full-data
reads for large aggregation tasks. It does not compress data losslessly into a
receipt: the receipt omits records; the snapshot preserves the original bytes.
Small or detail-heavy tasks can cost more. No universal token saving is promised.

Separately installed, explicitly invoked, no hooks, network calls, credentials,
subprocess execution, telemetry, or automatic interception of tool calls.
LLM Accuracy stays stateless. Deterministic Data owns definitions and routing;
this plugin supplies local execution and retrieval, not a replacement catalogue
or its evidence-receipt schema. Session Ledger remains independent.

## Use

Requires Python 3.9+ and a private local POSIX filesystem (Linux, macOS or WSL).
Linux/WSL is the tested pilot; native Windows and Cowork are unsupported.
Install from this marketplace, then invoke `/data-execution:local-data`.
Installation alone captures nothing. User confirmation of the source, scope and
storage location is needed before the first capture; subsequent authorized
captures in that scope can proceed without repeated confirmation.

Set a shell variable to the installed plugin directory:

```bash
PLUGIN=/path/to/plugins/data-execution
DATA_TOOL="$PLUGIN/scripts/local_data.py"
python3 "$DATA_TOOL" --help
```

Copy `examples/json.adapter.json` or `examples/csv.adapter.json` into your own
configuration directory and adapt it. Never edit the installed cache. The
examples contain only fictional scope and field names. They are not production
source bindings.

### Source adapters: CLI, MCP client, existing export

The adapter maps a JSON array or CSV rows to identity, amount, grouping and unit.
JSON paths are arrays of literal object keys, with no expressions or evaluation.
MCP clients can export a `structuredContent` object; configure `records_path`
and `complete.path` for that shape. Text-only MCP results need a reviewed client
bridge that extracts and validates their JSON first. This is not a native MCP
server, and it cannot divert responses from Claude's built-in MCP interface.
If the only available MCP tool returns its full output directly to Claude,
this plugin cannot prevent that initial context cost.

Capture a staged output only after its producer has exited successfully. For a
reviewed read-only exporter, the shell pattern is:

```bash
# Replace export-readonly with YOUR approved CLI or MCP-client export command.
# Its authentication and pagination remain your responsibility.
umask 077
stage=$(mktemp)
trap 'rm -f "$stage"' EXIT
if export-readonly > "$stage" 2>/dev/null; then
  python3 "$DATA_TOOL" capture --adapter /path/to/your.adapter.json --input "$stage"
else
  printf '%s\n' 'Source export failed; no snapshot captured.' >&2
  exit 1
fi
```

Do not print/cat the staging file, paste its contents into a tool argument, or
save a raw response that Claude already saw merely to claim context savings.
Do not pipe directly into capture: upstream exit status is not available to the
consumer. `--input -` is refused. Stderr is suppressed above to avoid leaking
source content; investigate failures with your source's normal safe diagnostics.

For an already completed, trusted export:

```bash
python3 "$DATA_TOOL" capture --adapter /path/to/your.adapter.json --input /path/to/export.json
# Use the returned snapshot ID and the exact adapter scope:
python3 "$DATA_TOOL" sum SNAPSHOT_ID --scope 'your-reviewed-scope'
python3 "$DATA_TOOL" detail SNAPSHOT_ID --scope 'your-reviewed-scope' --id RECORD_ID --field description
```

`sum` batches every group over the saved source without refetching. Amounts use
exact decimal arithmetic and output strings, never binary floats. No conversion
between major/minor currency units or currencies occurs. Use currency as the
grouping field for monetary data. Missing amounts, duplicate IDs, duplicate JSON
keys, invalid decimals and malformed CSV fail explicitly. Empty complete data
returns zero rows and no groups, not an invented zero-valued currency total.
Detail requires explicit IDs and fields. All JSON numeric values in detail
become strings before transport, including integers beyond JavaScript precision.
Raw snapshot bytes remain unchanged. The snapshot ID hashes raw bytes, adapter,
caveats, scope, completeness policy and timestamps; it excludes no envelope
fields and is stored as the filename, not inside its own hashed body.

### Completeness and scope

`complete.path` must resolve to a JSON boolean from your exporter. For a source
without a completeness field, `complete.asserted` is an explicit user/adapter
assertion. Neither option independently verifies pagination, source permissions,
filters, missing upstream records, or the producer's truthfulness. Never set
`asserted: true` merely because parsing succeeded. A bridge must check every
page and error before asserting completeness. Partial snapshots retain detail
with a `totals_status: withheld` marker; `sum` refuses them.

The scope string must identify source/account/mode, period/timezone, filters,
record grain and definition (use a reviewed versioned identifier if long).
It is a required exact-match guard, not authentication. Local same-user access
is trusted. `atomic_snapshot` is a separate declaration: complete pagination
does not mean all records were observed at the same instant. Receipts retain
this flag, capture time, unit and caveats. A capture time is not the source's
last-update time. Preserve source observation limits in the scope/caveats.

### Retention and storage

Default retention is **30 days**, matching Claude Code's documented default
when this pilot was designed. It is a plugin default, not a live inheritance
of `cleanupPeriodDays` or an organizational retention policy. Set a different
period on capture with `--retention-days N` (positive whole days up to 3650).
Existing snapshots retain their original expiry. Refreshing the source creates
a new immutable snapshot; it never silently updates a previous receipt.

Default location is `${CLAUDE_PLUGIN_DATA}/snapshots` when the host supplies it,
otherwise `~/.local/share/llm-accuracy/data-execution`. Use `--store /private/path`
**before** the command to select another location. Use the same location in a
new process/session to retrieve the snapshot, and retain its returned ID.
There is no automatic discovery or indexing of old session transcripts.

Reads refuse an expired snapshot. Capture and `purge` remove expired files;
there is no daemon, so idle storage can remain on disk beyond expiry. Schedule
`purge` yourself if calendar-time deletion is required. Corrupt or foreign JSON files block
cleanup and new captures in that store rather than being silently destroyed.
Existing intact snapshots remain queryable. Inspect the private store and repair
or explicitly delete the affected snapshot ID after investigation; non-snapshot
files must be moved out manually. Use a dedicated store directory. Delete operations do not erase backups or guarantee forensic
secure erasure. Interrupted writes may leave private `.capture-*` files;
inspect and remove these only when no capture is running.

```bash
python3 "$DATA_TOOL" purge
python3 "$DATA_TOOL" delete SNAPSHOT_ID
```

Snapshots contain plaintext-equivalent base64 data, not encryption. Keep the
store outside Git, shared folders and sync/backup locations unless permitted.
Directory permissions must be 0700 and files 0600; symlinked store paths are
rejected. Permissions protect against other users, not malicious processes
running as you. Use a trusted local filesystem, not shared/network storage.

Limits: 16 MiB source, 100000 rows, 256 MiB store, 16 KiB entire output packet;
100 requested detail IDs and 20 fields. Reaching a limit fails explicitly—no
silent truncation or eviction of unexpired snapshots. A failed oversized query
leaves its snapshot available for a smaller request. Missing, changed, expired
or wrong-scope sources must not be replaced from memory.

## Validation boundary

Tests use newly constructed synthetic data only. Local lifecycle, precision,
projection and byte-accounting results are distinct from model token usage,
provider correctness or live integration validation. See
[the implementation plan](../../docs/data-execution-plan.md) and
[the synthetic usefulness experiment](../../docs/data-execution-validation.md).
