---
name: clarify
description: Resolve missing choices that materially change a data analysis, factual answer or requested deliverable, or when the user asks to clarify assumptions. Use automatically for consequential ambiguity and on explicit invocation. Skip choices already settled by the user or authoritative context, and harmless implementation details.
---

# Clarify

Resolve consequential ambiguity before relying on an assumed answer. This is an
advisory workflow, not a guarantee that all assumptions or errors are found.

First inspect the request, earlier answers, available sources and any approved
definitions. Do not ask the user to repeat a settled choice or supply information
you can obtain with available, authorized read-only tools. Data can reveal fields
and alternative results; it cannot decide which business meaning the user intends.

For data work, check only unresolved choices that affect the requested result:
metric and units, population and exclusions, grain or duplicate handling,
denominator, dates and time zone, comparison, source/version and success criterion.
If useful and feasible, calculate alternatives from available evidence to explain
the effect of the choice. Do not invent figures or require a full analysis before
asking a simple defining question.

Use the host's available interactive question tool in preference to ordinary
chat. Inspect its actual schema and mode restrictions: tools may be named
`AskUserQuestion`, `request_user_input`, `request_user_input_async`, or something
else. Use an asynchronous question when supported so independent work can
continue. Do not change modes, install an integration or invent a tool to ask.

For a few meaningful alternatives, offer concise, distinct multiple-choice
answers with a brief consequence for each. Put a recommendation first only when
the user's goal or evidence supports it; label and explain that recommendation.
Allow a free-text alternative through the host's built-in facility. If the
choice is open-ended, use its free-text question instead of forcing false options.
Follow the host's question/option limits and avoid duplicating its built-in Other
option. If no suitable question tool is available in the current mode, ask one
short question in chat, with numbered choices where useful. Do not repeat a tool
question in chat.

Ask the smallest set of questions needed to remove the material ambiguity.
Wait for the answer before dependent calculations or conclusions; continue
independent work where useful. A recommended or preselected option, elapsed time,
an empty response or dismissal is not an answer. If the user explicitly asks you
to proceed with assumptions, state the chosen assumptions and keep dependent
results conditional. Missing source evidence still remains unavailable.

Apply the answer to the task and retain its meaning in the conversation or
existing task brief. Do not create a new persistent store. Revisit the choice only
when the user changes it or new evidence creates a material conflict. If nothing
material remains unresolved, proceed without a ceremonial confirmation.
