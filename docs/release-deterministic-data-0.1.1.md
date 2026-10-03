# Deterministic Data 0.1.1

This patch makes `data-routing` step aside when you have no catalogue. Before,
the skill engaged on any data or metric question. With no catalogue entry to
route to, it withheld the answer behind a "catalogue gap" receipt, even when
the figure could be computed from a file you supplied.

**What changes for you.**

- **Narrower trigger:** the skill is for users who have a deterministic-data
  catalogue, or who ask to route a question through one.
- **No catalogue:** the skill says so in one sentence, then answers as ordinary
  analysis, labelled non-canonical, with no evidence receipt. The Output
  contract applies only when a catalogue exists.
- **Validator command:** given as one literal template. Model-rewritten shell
  forms of the old description tripped host command-safety checks.

With a catalogue, routing is unchanged: a question whose definition the
catalogue lacks still stops at the catalogue gap.

**Evidence and limits.** These are screens on one synthetic invoices fixture,
not powered comparisons; see the
[validation receipt](validation/deterministic-data-0.1.1-2026-10-03.json).

- **Before, no catalogue:** the skill withheld 6/6 answers (Sonnet and Opus,
  n=3 each), each citing a catalogue gap.
- **After, no catalogue (n=1 per model):** both models answered from the file,
  their figures matched an independent recompute, and nothing out of scope
  leaked.
- **Catalogue present:** across 12 runs on the original and fixed skill, with a
  synthetic catalogue lacking the asked-for definition, the skill engaged and
  withheld at the gap 12/12, with 0 leaks.

To update, run `claude plugin marketplace update llm-accuracy` and
`claude plugin update deterministic-data@llm-accuracy`, then restart Claude
Code or run `/reload-plugins`.
