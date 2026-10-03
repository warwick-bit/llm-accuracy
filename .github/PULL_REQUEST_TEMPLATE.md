## Summary

## Validation

- [ ] `python3 -m pytest -q`
- [ ] Marketplace and plugin manifests parse.
- [ ] Retained hooks compile.
- [ ] Distribution boundary checked.
- [ ] `python3 scripts/check_compatibility.py`; source/version bindings current.
- [ ] Linux/WSL, Windows with/without Git Bash, macOS, Desktop Chat/Code/Cowork considered.
- [ ] Installed-host gaps explicitly marked untested; no historical pass reused.

## Privacy and distribution boundary

- [ ] No credentials, customer data, raw prompts, provider payloads, or private logs are included.
- [ ] The change adds no telemetry or server-side storage, preserves Session Ledger's local-only, same-session boundary, and explicitly documents any changes to opt-in local persistence.
- [ ] Any new accuracy claim is bounded and backed by current evidence.

## Follow-up

- [ ] Clean Claude Code installation smoke is recorded when a release is proposed.
- [ ] `python3 scripts/check_compatibility.py --release` before release/tagging.
