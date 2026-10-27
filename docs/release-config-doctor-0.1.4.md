# Config Doctor 0.1.4 preview

After showing the report, Doctor now groups useful remaining checks into a
clearly described follow-up choice. It explains what is included and what will
remain unchecked, separating checks with different access, risk or cost. The
question stays short and uses everyday language; technical details stay in the
supporting report. Checking still requires the user's choice, and applying changes
remains a separate decision.

Headlines and status labels must preserve the evidence limits. An offline check
that produces a reminder does not establish delivery to the AI; observing one
startup reminder does not verify every other reminder or whether the AI follows
them. A recommendation to keep a control can still have unresolved checks.

Use the [startup guide](../tools/config-doctor/README.md) or the
[0.1.4 preview release](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.4).
The agent fetches the released ZIP. Python 3.11+ is required.

This is guidance in the existing workflow, with no new runtime, schema,
dependencies or test framework. Qualification uses the existing Doctor contract
checks from the extracted ZIP, archive/source and local-link checks, independent
review and required repository CI. See the published release for completed results.
Guidance and synthetic screens do not certify adherence or question-tool behavior
in every live client. Prior release assets and plugin packages remain unchanged.
