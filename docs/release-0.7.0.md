# LLM Accuracy 0.7.0

Adds `/llm-accuracy:technical-review model=<available Claude model>`: an explicit
review of a complete technical draft against supplied, attributed evidence.
Normal reminders, custom phrase triggers and bypasses are unchanged.

The reviewer checks for unsupported assertions, missing requested content and
unnecessary hedging. It returns findings tied to exact input spans and evidence
IDs. The primary assistant must recheck those findings before using them.
Failed reviews are reported as unavailable. Empty findings mean no issue found
within the packet, not verified accuracy or permission to deploy.

## Upgrade and try it

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

Deterministic tests exercise input, output, identity and error handling. A clean
local marketplace/ZIP smoke and native skill invocation ran on Claude Code
2.1.280 under Linux/WSL. The initial narrow test permissions prevented the
helper from running; correcting those permissions allowed one review and the
required presentation receipt. Product permissions were not changed.
[Installation receipt](validation/technical-review-install-2026-09-23.json).

Native Windows and Cowork execution of the new command remain unverified.
The reviewer cannot authenticate sources, establish packet completeness or
certify factual correctness. General improvement on real answers has not been
demonstrated. No packets or answers are saved by the helper; parent conversation
and provider retention still apply.
