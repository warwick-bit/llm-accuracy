## Summary

## Validation

- [ ] `python3 -m pytest -q`
- [ ] Marketplace and plugin manifests parse.
- [ ] Retained hooks compile.
- [ ] Private-preview distribution boundary checked.

## Privacy and preview boundary

- [ ] No credentials, customer data, raw prompts, provider payloads, or private logs are included.
- [ ] The change does not add telemetry, server-side storage, prompt/tool-output persistence, or a session ledger.
- [ ] Any new accuracy claim is bounded and backed by current evidence.

## Follow-up

- [ ] Clean Claude Code installation smoke is recorded when a release is proposed.
