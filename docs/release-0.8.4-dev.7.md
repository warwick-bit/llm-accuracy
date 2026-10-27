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

Install through the **LLM Accuracy marketplace**; no ZIP download is needed.

1. In Claude, open **Customize → Plugins**. In Cowork, open the Cowork tab first.
2. Choose **Add marketplace** from **Add** (or the **+** beside Personal plugins), then **Add from a repository**.
3. Enter `https://github.com/warwick-bit/llm-accuracy`.
4. Select **LLM Accuracy** from that marketplace and install it.
5. Confirm version **0.8.4-dev.7**, then start a fresh conversation.

Clarify is included in LLM Accuracy; it is not a separate plugin. If the marketplace
is already added, refresh/sync it and update the existing LLM Accuracy installation.
Organization policy may control marketplace access. See
[Claude's marketplace instructions](https://support.claude.com/en/articles/13837440-use-plugins-in-claude).

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
