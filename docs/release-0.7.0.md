# LLM Accuracy 0.7.0

**Unreleased candidate:** the [completed conversational challenge](technical-review-conversation-validation.md)
did not demonstrate added detection benefit. Keep the PR draft; do not promote
this candidate as a general accuracy fix.

Adds `/llm-accuracy:technical-review model=<available Claude model>`: an explicit
review of a complete technical draft against supplied, attributed evidence.
Normal reminders, custom phrase triggers and bypasses are unchanged.

The reviewer checks for unsupported assertions, missing requested content and
unnecessary hedging. It returns findings tied to exact input spans and evidence
IDs. The primary assistant must recheck those findings before using them.
Failed reviews are reported as unavailable. Empty findings mean no issue found
within the packet, not verified accuracy or permission to deploy.

## Upgrade instructions for a future publication

Version 0.7.0 is not published. These commands currently fetch the released
version, not this candidate. Use them only if this candidate is later published.

In Claude Code:

```text
/plugin marketplace update llm-accuracy
/plugin update llm-accuracy@llm-accuracy
/reload-plugins
/llm-accuracy:accuracy-doctor
```

Check the doctor reports package version 0.7.0. Start a fresh session if the host
still shows an older version. These instructions do not verify another machine's
installed configuration.

Choose a reviewer model your local Claude account supports, then invoke:

```text
/llm-accuracy:technical-review model=<your-model>
Question: What is the incident status?
Draft: Status: Open. Local tests reportedly pass.
Evidence e1, user report: Local tests pass; production is unchecked.
No tracker status was supplied. The draft author model is unknown.
```

The expected useful finding is the unsupported recorded `Open` status. The
reported local test result should remain valid. The output should preserve the
Checked / Gap / Next receipt and keep author identity unknown. Repeat with an
authoritative tracker explicitly reporting Closed and a draft that attributes
Closed to it while leaving service recovery unverified; that narrower fact
should remain reportable. Model behavior is fallible; these are checks to inspect,
not guaranteed outputs.

A signed-in local Claude Code CLI and Python 3 are required. Each explicit review
adds latency and account usage. Your usual command permissions apply; approve
the displayed helper command if prompted. The command never changes them.
There is no automatic retry or model substitution. A missing/unavailable model,
authentication failure or timeout must remain an unavailable review.

## Validation boundary

The authored pilot matched ten cases in both initial and reversed-order runs.
This is development evidence, not a held-out accuracy comparison. Earlier
unsuccessful reminder candidates and reviewer pilots remain failed and separate.
[Details and limitations](technical-review-pilot.md).

Deterministic tests exercise input, output, identity and error handling. A fresh
local marketplace/ZIP smoke and native skill invocation passed on Claude Code
2.1.280 under Linux/WSL at `53bfdaab0bfcf06d4ed4323af9874d061fbb6d81`, after the
transport, error-classification and Unicode framing fixes. Default/custom/bypass behavior and
native evidence-receipt rendering passed. An additional unidentified host
component in native/custom/bypass sessions limits isolation claims.
[Final-source installation receipt](validation/technical-review-install-final-2026-09-23.json).
The [prior source receipt](validation/technical-review-install-current-2026-09-23.json)
remains unchanged.
The [earlier receipt](validation/technical-review-install-2026-09-23.json) preserves
initial narrow-permission failures; product permissions were not changed.

The initial direct-inspection conversational run attempted four scenarios. Three were invalid
because of host errors or timeouts; one single-turn repository inspection and
review completed with no identified defect. No valid multi-turn reviewer result
or added detection benefit was established. [Full result](technical-review-conversation-validation.md).
Error diagnosis now excludes IDs, successful answers and other non-error content
from authentication/rate-limit classification; these remain heuristic indicators.
An altered-context follow-up initially hit an account usage limit. After access
reset, the final declared pass completed all three multi-turn conversations and
reviews. Fable returned no findings: two final answers had no material issue
identified, while the closure case retained a disputed nondeployment/status
inference. No added detection benefit was demonstrated; the experiment is closed
without further prompt/model/rubric retries. The plain-text clarification envelope
and user-authorized concurrent review load limit generalization. Earlier failed
attempts remain recorded. The final-source authenticated smoke also passed.

Native Windows and Cowork execution of the new command remain unverified.
The reviewer cannot authenticate sources, establish packet completeness or
certify factual correctness. General improvement on real answers has not been
demonstrated. No packets or answers are saved by the helper; parent conversation
and provider retention still apply.
