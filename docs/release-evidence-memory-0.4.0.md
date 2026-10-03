# Evidence Memory 0.4.0

**Answers to Claude's questions are now remembered.** When Claude asks you
something with `AskUserQuestion` and you answer, Evidence Memory stores the
answer as `decision` state: the question, your choice and any note you added.
Asking the same question again replaces the earlier answer. Decisions appear in
the post-compaction restore packet with the rest of the current state, inside
its existing 20-item, 2,200-character budget.

**Why.** In the maintainer's own Claude Code transcripts, compaction summaries
kept 98.3% of answers after one compaction, but only 75.6% after two, 56.8%
after three and 52.1% after four or more. Before this release, neither Evidence
Memory nor Session Ledger stored answers, and enabled indexes held no
model-written state, so capture is automatic once the plugin is enabled.

**What it changes for you.** Enabling the plugin now also stores your answers
to Claude's questions locally, alongside external tool results. Re-reading a
transcript adds nothing. Disable, clear and the 30-day expiry apply as before.

**Evidence and limits.** In live screens with an earlier prototype's restore
packet, Claude reused stored choices when asked (6/6, against 0/6 without),
applied them unprompted (6/6), followed a new instruction over a stored one
(4/4), and did not carry them into a question about an unrelated file (0/8).
In one session with three real compactions, on code from before the final
capture fixes, the plugin stored all 4 answers and restored them after each
compaction; in two sessions without the plugin the summaries also kept the
choices at that size, so live benefit in long sessions remains unmeasured. A clean-profile marketplace install matched the committed files and
recorded a decision through a real compaction. See the
[validation receipt](validation/evidence-memory-0.4.0-2026-10-03.json).

**Not covered.** Decisions typed as ordinary chat messages, transcripts
rewritten in place (see the
[plugin guide](../plugins/evidence-memory/README.md)), and Codex, whose question
tool returns only an acknowledgement. An index from an earlier version that is
too full to add the answer tables keeps capturing evidence without answers.

To update, run `claude plugin marketplace update llm-accuracy` and
`claude plugin update evidence-memory@llm-accuracy`, then restart Claude Code or
run `/reload-plugins`.
