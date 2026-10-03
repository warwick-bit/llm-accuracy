# LLM Accuracy 0.7.2

This patch changes what the business-ambiguity reminder asks for, and adds one
more kind of question it recognises.

**What changes for you.**

- **Explore first:** when a question has more than one reasonable reading and
  the data is available, the reminder now asks Claude to inspect the data
  first, show how each choice moves the answer, then ask one short
  clarification limited to the choices that change it, giving the figure each
  option produces. Before, it asked Claude to clarify without looking first.
- **New-customer counts:** questions such as "How many new customers did we get
  in July?" now get the reminder. Its guidance names what makes a customer new
  (first payment, sign-up or trial; whether returning or reactivated customers
  count), which test, internal, trial and merged accounts to exclude, the time
  zone and window edges, and whether to count accounts, people or rows.
- **Stays quiet when the question is already defined:** a count that names a
  time zone (UTC, a named zone such as "Sydney time", an abbreviation such as
  AEST, or an IANA name such as Australia/Sydney), says "defined as",
  "distinct" or "excluding", or gives a first-payment rule gets no reminder. So
  do development counts (test fixtures, seed or mock data, a test, dev, QA, CI,
  staging or local database, Redis, a schema migration, or a named code file or
  PR), other
  subjects such as new tickets, and prompts with the `# analysis-ok` bypass.
  Only the first 2,000 characters are read for these signals, so a file pasted
  after the question does not silence the reminder.
- **Fires when a silence signal is ambiguous:** a missed reminder costs more
  than an extra one. A named data file such as `signups.csv` still gets the
  reminder, and so do business events ("since the pricing page deploy", "after
  the CRM migration", "the Next.js Conf sponsorship"), region pairs such as
  Australia/NZ or North America/Europe, words with a business meaning ("unique
  promo codes", "light fixtures", "home staging", "the first-order discount",
  "time-limited"), and abbreviations that also name other things (CST, EST,
  IST, BST).

The four existing reminders (revenue, best customers, marketing channel and
onboarding activation) keep their own guidance and are each 152 characters
longer. The new-count reminder is 1,049 characters against its 1,500 cap.

**Evidence and limits.** These are screens on one synthetic fixture, not
powered comparisons; see the
[validation receipt](validation/claude-code-ambiguity-explore-0.7.2.json).

- **Fixture:** a synthetic `signups.csv` in which each trap moves the July
  count to a different value: 43 by the reference definition, 41 in UTC, 48
  with test accounts, 46 with merged accounts, 47 counting trials, 34 counting
  sign-ups, 49 with returning customers, 54 counting rows and 45 with undated
  rows. Every figure in every reply was checked against these values.
- **Vague question (Sonnet and Opus, n=3 per model and version):** with 0.7.2
  the reminder fired 6/6, and every reply opened with a conditional answer and
  a direct question about the definition, listing the options with their
  counts. With 0.7.1 no reminder fired, and every reply opened with 43 as the
  answer and listed alternatives after it. All 12 replies gave 43 under the
  definition they stated. Factual slips: 2 of 6 replies with 0.7.2 and 1 of 6
  with 0.7.1, too few to compare.
- **Precise question (definition, exclusions and time zone given; n=1 per
  model and version):** the reminder stayed silent 4/4, and all four replies
  gave 43; one 0.7.1 reply had a factual slip.
- **What this does not show:** that answers become more accurate, that people
  prefer a question to an answer, or how the reminder behaves on other
  wordings, other models or real data. The pattern recognises questions that
  open "How many new …" with a verb such as "did we get" or "were there";
  other wordings, such as "How many new users signed up in July?", do not get
  the reminder yet. Every reply in both versions inspected
  the file before answering, so the change is in how the answer is framed, not
  in whether Claude looks.

**Installation.** A clean temporary Claude Code 2.1.288 profile on Linux/WSL
installed 0.7.2 from a local-path marketplace; the installed files matched the
committed package byte for byte, and the default, bypass and release-archive
sessions each received the expected reminders. See the
[installation smoke](validation/claude-code-smoke-0.7.2.json). The isolated
bundle smoke on the same commit passed every required Code check and is
recorded as the `code-wsl` live pass in the
[compatibility record](validation/compatibility-candidate.json); the native
Linux, macOS and Windows installation rows come from CI.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a new Claude Code session or run `/reload-plugins`, then confirm package
`0.7.2` in `/llm-accuracy:accuracy-doctor`. See the [install guide](INSTALL.md).
