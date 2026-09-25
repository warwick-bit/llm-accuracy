# Session Ledger 0.2.7

This patch preserves UTF-8 text from hook input on Windows, isolates malformed
local records so they cannot block another session, and holds the session lock
while pruning expired records. Rolling history now reconciles transcript rows
chronologically: re-reading an unchanged long transcript no longer makes older
evicted rows look new and rotate out more recent decisions. It also handles
CRLF appends and repeated identical rows without duplicating them.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update session-ledger@llm-accuracy
```

Confirm version `0.2.7` and enabled state in `/plugin`, then start a new Claude
Code session. See the [Session Ledger guide](../plugins/session-ledger/README.md).

## Limits

The rolling record remains capped at 64 KiB, with a 16 KiB cap per entry and a
32 KiB compact-summary cap. New entries can evict older entries; a byte-limit
notice means some history was omitted or shortened, and it may recur as a long
session keeps adding text. The plugin does not store exact tool results. Use the
separate, explicit opt-in Evidence Memory plugin when you need to retrieve
logged results from the current session. No live answer-accuracy or token-saving
improvement has been established.
