# LLM Accuracy 0.6.6

This patch changes how the Checked / Gap / Next footer is laid out. The claim
fidelity reminder now asks for a `---` divider (with a blank line before and
after) followed by three bold-labelled bullets:

```markdown
---

- **Checked:** actual checks or supplied evidence, with scope
- **Gap:** remaining unknowns (or none)
- **Next:** smallest useful check or action (or none)
```

The blank line before `---` matters: without it, Markdown renders the previous
line as a heading instead of drawing a divider. The `claim-fidelity`,
`verify-technical` and `accuracy-doctor` skills describe the same layout, as
does the bundled evidence-discipline reference. That reference also applies it
to the labels it asks for at the end of other consequential factual answers
(Source, Time window, Scope or denominator, Caveat or data gap, Direct evidence
versus inference, Next step). The footer's fields, when it applies and what each
field means are unchanged. Detection, bypasses and the other hooks are
unchanged.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a new Claude Code session or run `/reload-plugins`, then confirm package
`0.6.6` in `/llm-accuracy:accuracy-doctor`. ZIP users can use the
`llm-accuracy-0.6.6.zip` release asset. See the [install guide](INSTALL.md).

## Validation and limits

Wiring tests pin the new template in the injected reminder and keep it within
the 1,500-character budget. The technical harness's footer check already
accepted bold bullet labels, and a new test confirms it accepts the divider
form. This changes formatting only; no live model run measured whether
footers now follow the new layout more often.
