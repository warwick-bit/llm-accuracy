## Summary

## Validation

- [ ] `python3 -m pytest -q`
- [ ] Marketplace and plugin manifests parse.
- [ ] Retained hooks compile.
- [ ] Distribution boundary checked.

## Privacy and distribution boundary

- [ ] No credentials, customer data, raw prompts, provider payloads, or private logs are included.
- [ ] The change does not add telemetry, server-side storage, prompt/tool-output persistence, or alter Session Ledger's reviewed local-only, same-session boundary.
- [ ] Any new accuracy claim is bounded and backed by current evidence.

## Follow-up

- [ ] Clean Claude Code installation smoke is recorded when a release is proposed.
