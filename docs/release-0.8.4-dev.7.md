# Accuracy 0.8.4-dev.7 — Clarify team preview

This preview adds Clarify to LLM Accuracy. It asks the model to resolve missing
definitions and inputs before reporting a result, use the host's interactive
question tool for meaningful choices, and follow the user's language preferences
with plain English as the default. Existing context should settle questions
where possible; explicit definitions and requests for alternatives should proceed
without unnecessary confirmation.

Claude Code's existing session mode now adds a short clarification reminder on
each request. Existing disable controls and targeted-only mode remain available.
Codex remains skills-only, with no Claude hooks or configuration requirements.
No new persistence, telemetry, connector or external service is added.

## Install for team testing

Download `llm-accuracy-0.8.4-dev.7.zip` from the
[preview release](https://github.com/warwick-bit/llm-accuracy/releases/tag/v0.8.4-dev.7).
In Claude Chat or Cowork, open **Customize → Plugins** and use the custom-plugin
upload option. In Cowork, open the Cowork tab first. Verify the installed version
is **0.8.4-dev.7**, then start a fresh conversation. Clarify is included in LLM
Accuracy; it is not a separate plugin. Organization policy may control sharing
and installation. See [Claude's installation and sharing instructions](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

Claude Code users can add the repository marketplace and install the package:

```text
/plugin marketplace add warwick-bit/llm-accuracy
/plugin install llm-accuracy@llm-accuracy
```

For an existing installation, refresh the marketplace and update LLM Accuracy
through the plugin manager, then restart the session. Codex users can add
`https://github.com/warwick-bit/llm-accuracy` in their plugin marketplace and select
LLM Accuracy. Verify the version after installation or update; an older cached
package does not contain this preview's instructions.

## Known limits and useful tests

Desktop Chat and Cowork support remains experimental. User testing confirmed
selectable questions in both surfaces, but automatic clarification still missed
an ambiguous processing-time question in Chat. It showed alternatives and
recommended a definition without asking. This preview does not guarantee skill
invocation, selector rendering, or an improvement in overall answer accuracy.
Chat does not run hooks; Cowork hook delivery remains unverified.

Explicitly select Clarify or begin with `Use llm-accuracy:clarify.` when testing
its workflow separately from automatic skill selection. A missing number may
need a typed follow-up after a selectable definition question. A choice such as
"I'll type the amount" is not the amount and must not permit a real calculation.

Use fresh synthetic conversations in Chat and Cowork separately:

1. Ask for an average from records containing both successful and failed work,
   without defining which to count. Expect a definition question before a chosen
   result. Answer the question and check the resulting population and arithmetic.
2. Repeat with "successful work only" specified. Expect the calculation directly.
3. Explicitly invoke Clarify and ask for a profit margin with revenue but no costs.
   Expect a cost-definition choice and a request for the missing amount; no actual
   margin until the amount is supplied for the matching period.

Report the host, plugin version, exact synthetic prompt, whether a selector
appeared, selected answer and resulting response. Share no private business data.

## Qualification boundaries

The [live bundle receipt](validation/claude-bundle-smoke-0.8.4-dev.7.json) and
[Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.4-dev.7.json)
record the actual source tested on native Windows. The compatibility record
separates live Code evidence from native installed CI checks and Desktop UI.
Publication requires the existing release gates, including all four native
installed targets. These checks do not certify Desktop rendering or model
adherence rates. Complete Desktop lifecycle qualification remains outstanding.
