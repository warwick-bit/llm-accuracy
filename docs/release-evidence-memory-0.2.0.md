# Evidence Memory 0.2.0

Enabling Evidence Memory in Claude settings now starts local capture automatically
in each session. You no longer need to run `/evidence-memory:memory enable` every
time. The first session hook starts at a fresh cutoff, so enabling the plugin
mid-session does not silently import earlier transcript rows.

Exact tool results may contain sensitive data. The plugin is still disabled by
default when installed. **If you already enabled Evidence Memory, updating to
0.2.0 starts capture automatically at the next session start or prompt.** To
keep capture off, disable the plugin in `/plugin` before updating; re-enable it
when you want automatic capture. Disabling the plugin stops future sessions.
Within one session, `/evidence-memory:memory disable`, `clear`, or `begin-plan`
deletes its evidence and stops automatic capture there; an explicit `enable`
resumes it without reimporting pre-cutoff rows. Session Ledger remains separate.

To update, run `claude plugin marketplace update llm-accuracy` and
`claude plugin update evidence-memory@llm-accuracy`, then restart Claude Code or
run `/reload-plugins`. See the [install guide](INSTALL.md) and
[plugin guide](../plugins/evidence-memory/README.md).

Synthetic hook tests cover automatic start, no pre-enable backfill, and all
session stop actions. Hook timeouts are 10 seconds to allow cold startup and a
bounded initial sync. Live long-session accuracy and token savings remain
unmeasured.
