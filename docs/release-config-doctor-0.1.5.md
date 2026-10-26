# Config Doctor 0.1.5 preview

Doctor's short summaries must preserve the words that explain a recommendation,
including source restrictions and uncertainty. Before accepting or rejecting a
finding, check the exact source and full finding. A possible wording problem can
justify an optional hypothesis without establishing a behavior failure.

Doctor must also check its proposed test before using it to judge a change.
Expected answers need adequate inputs and a defined metric: a fall in total user
counts alone does not establish churn. Check the calculation and its meaning
separately, correct invalid expectations and leave behavior unverified until the
corrected check runs.

Use the [startup guide](../tools/config-doctor/README.md) or the
[0.1.5 preview release](https://github.com/warwick-bit/llm-accuracy/releases/tag/config-doctor-v0.1.5).
Python 3.11+ is required. The agent fetches the released tool for you.

This is a small guidance update, with no new runtime, schema, dependencies or
permanent tests. Qualification uses the existing Doctor contracts from the
extracted ZIP, archive/source and link checks, a bounded synthetic model screen,
independent review and required repository CI. See the release for completed
results. These checks do not establish reliable adherence in every session.
Plugin packages and earlier release assets remain unchanged.
