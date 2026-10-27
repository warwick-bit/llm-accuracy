---
name: clarify
description: Use before interpreting supplied data or reporting a metric, average, rate, growth or comparison, including apparently straightforward calculations. Check definitions and missing inputs; ask only when an unresolved choice materially changes the result. Also use for ambiguous factual requests or deliverables and explicit requests to clarify assumptions. Proceed directly when context settles the meaning and inputs.
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

When the user asks for one result and an unresolved definition changes that
result, ask before choosing a headline answer. A familiar convention or a
plausible use for each alternative does not establish the user's intended meaning.
Keep definition choices neutral unless their stated goal supports a recommendation.
Calculating or showing both interpretations does not settle the user's intended
meaning; use those
alternatives to help frame the question. If the user requested both interpretations
or explicitly authorized assumptions, follow that request without an extra
definition question.

When a question is needed, make an actual call to the host's interactive question
tool before ending the turn. Writing options in a chat message is not a tool
call. Check the tools available in this conversation and their actual schemas
and mode restrictions; do not infer availability from the app name. The tool
may be named `AskUserQuestion`, `request_user_input`, `request_user_input_async`,
or have another name or namespace. Use the available question capability even
when its name differs from these examples.

In a Codex CLI terminal, prefer `request_user_input` for the native selectable
menu when permitted. In other clients, prefer an asynchronous question when
the client supports rendering its interactive choices, so independent work can
continue. Reading this skill or describing the intended question does not
complete this step. A listed tool or an `accepted` result does not prove that a
selector appeared. If the user reports no selector, try another available,
permitted question tool; do not repeat the failed route. Do not change modes,
install an integration or invent a tool to ask.

For a few meaningful alternatives, offer concise, distinct multiple-choice
answers with a brief consequence for each. Put a recommendation first only when
the user's goal or evidence supports it; label and explain that recommendation.
Allow a free-text alternative through the host's built-in facility. If the
choice is open-ended, use a free-text question if the tool supports one.
When a request needs both a definition choice and a missing value, keep the
definition as selectable options and collect the actual value through a suitable
free-text input or a follow-up. If the tool requires multiple choices but only
an amount, date or other open value is missing, ask a short chat question instead
of inventing choices, ranges or an "I'll type it" option. Such a selection is not
the missing value. A partial answer settles only what the user actually supplied;
retain that part and ask only for what is still needed. Missing numbers do not
turn a meaningful
definition choice into an entirely prose question. Follow the host's question
limits and avoid duplicating its built-in Other option. Only fall back to a
short chat question when no suitable tool is available or permitted, or the
available tools failed. Do not repeat a tool question in chat.

Ask the smallest set of questions needed to remove the material ambiguity.
Follow the user's configured language, tone, accessibility and question-format
preferences, within the host tool's constraints. Otherwise use plain English:
short questions, familiar words and choices that explain the practical difference.
Avoid unexplained jargon and internal implementation details; explain a necessary
technical term briefly. Preserve the intended meaning when simplifying a question.
Wait for the answer before dependent calculations or conclusions; continue
independent work where useful. A recommended or preselected option, elapsed time,
an empty response or dismissal is not an answer. If the user explicitly asks you
to proceed with assumptions, state the chosen assumptions and keep dependent
results conditional. Missing source evidence still remains unavailable.

Apply the answer to the task and retain its meaning in the conversation or
existing task brief. Keep the selected measure, units, population and period in
the result. Plain-English labels must preserve the calculation: a total is not
a per-item figure without the relevant count. Do not add a causal diagnosis or
claim that a definition is usual without supporting evidence.
Do not create a new persistent store. Revisit the choice only
when the user changes it or new evidence creates a material conflict. If nothing
material remains unresolved, proceed without a ceremonial confirmation.
