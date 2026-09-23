# Session Ledger 0.2.6

Session Ledger now keeps capturing and restoring the same session when its
working directory changes. An explicit plan reset excludes transcript rows
at or before its timestamp cutoff. Host-marked summary copies and recognised
whole metadata envelopes no longer enter the rolling transcript record.

## Install or update

Follow the [setup instructions](../plugins/session-ledger/README.md#install-and-enable).
Claude Code 2.1.78 is the feature floor for the required hook/storage APIs;
use a current release. The native Windows smoke used 2.1.281. Python 3.9 or
later and a POSIX-compatible hook shell such as Git Bash are also required.
Enable the plugin explicitly and start a fresh session after installation.

## Validation

- 585 automated tests, Ruff, manifest parsing and hook compilation passed.
- Clean temporary-profile marketplace installation matched the hook source and
  captured/restored a synthetic decision across directory changes on WSL.
- One native Windows Claude Code 2.1.281 smoke produced 16 hook receipts:
  capture continued after directory navigation; both synthetic markers were
  restored after compaction; the compact summary was saved; an explicit new
  plan captured a new marker; a fresh session contained none of the old markers.
  All recorded hook processes exited successfully.
- The Windows harness used a separately named, enabled QA plugin with an
  observer wrapper around byte-identical production hook code. This is live
  hook-delivery evidence, not a production marketplace-install test on Windows.
  Only scalar checks were reviewed for the receipt; no transcript or stored
  ledger contents are included here.

## Limits

A plan reset clears stored history, not Claude's conversation. The Windows
smoke confirmed that a later assistant reply can restate earlier markers and
be captured in the new plan. Use a fresh session for conversation isolation.
Unmarked host output remains eligible for capture. Bounded newest-first
restoration can omit older decisions. This release does not establish an LLM
accuracy improvement or guarantee behavior on every machine.
