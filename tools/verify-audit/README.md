# Optional native Claude audit adapter

This repository tool is separate from the stateless Accuracy plugin and is not
included in plugin archives. Use it only with authorization for two model calls.
It uses the existing native Claude client and inherited profile/authentication;
it installs nothing, adds no hook, loads no MCP server and never retries.
Selected source/answer text is sent through that client. Working and full
receipts are saved only in the requested new task output directory.

Run `python tools/verify-audit/audit_answer.py --source source.md --candidate
answer.md --output-dir new-audit-directory`. Repeat `--source` for original
sources. On Windows the caller must launch Python hidden; both native client
children use CREATE_NO_WINDOW. `--claude` selects only the already authorized
native executable. No new provider, credentials or profile switch is supplied.

The first model produces its own compact claims/scenarios. The plugin's generic
offline helper binds quotes, rejects omitted explicit if-markers and executes
literal equations. The second model audits the whole unchanged candidate and
sources. Failures stop; source inputs stay read-only. The final audit is read
back with a hash. Completion means process and literal checks completed, never
that source truth, completeness, scenario admissibility or semantic accuracy
is certified. Independent review remains necessary for consequential delivery.
