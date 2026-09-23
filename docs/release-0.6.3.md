# LLM Accuracy 0.6.3

Maintenance release for the optional Claude host probe used by diagnostics and
validation tooling.

- Input delivery now shares the probe deadline, including when the child stops
  reading its first or a later input. Cleanup leaves stdin with its feeder.
  Completion waits for the feeder so a late write failure cannot become success.
- Failure classification uses failed-result diagnostics and stderr, preserving
  early authentication errors without treating unrelated IDs or successful
  answer text as authentication or rate-limit evidence. Categories remain
  heuristic.
- JSONL parsing preserves Unicode line separators inside response strings while
  continuing to accept LF and CRLF framing.

Automatic reminders, custom phrases and evidence-footer guidance are unchanged.
The experimental second-model reviewer is excluded. This release does not
establish improved factual accuracy or fix provider-side tool-call errors.

## Update and check

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a fresh Claude Code session and run `/llm-accuracy:accuracy-doctor`.
Confirm package `0.6.3`. Offline probes check the package and user controls;
they do not prove current-session activation or factual accuracy. The optional
live check tests delivery in a separate isolated session.

For ZIP installations, replace the installed archive with
`llm-accuracy-0.6.3.zip` from this release.

## Scope and validation

All 574 local tests pass, along with Ruff, manifest parsing, Python compilation
and all three distribution profiles. Regression coverage includes blocked first/later input, early errors, cleanup
ownership, misleading non-error text, explicit session limits and Unicode
separators through real subprocess streams. See the release PR for current
local and CI results. A [clean-profile marketplace and ZIP smoke](validation/claude-code-smoke-0.6.3.json) passed on Claude Code 2.1.280, Linux/WSL: installed files matched the committed source, and default/custom/bypass hook counts and acknowledgements matched expectations. Custom and bypass sessions reported an additional unidentified host component; this is functional installation evidence, not fully isolated causal evidence.

Native Windows model execution, Cowork and the affected remote configuration
require separate runtime validation. The plugin remains advisory.

Shared advisory hooks and evidence doctrine are unchanged from 0.6.2. These
transport fixes are intentional generic downstream maintenance; no private
runtime policy, provider data or transcripts are included.
