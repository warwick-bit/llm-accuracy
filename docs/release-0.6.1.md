# LLM Accuracy 0.6.1

Technical evidence-sufficiency answers now explicitly request the compact
Checked / Gap / Next footer, including when rejecting or withholding a claim.
The reminder sits after the other fidelity guidance and distinguishes supplied
evidence from checks the assistant actually performed. Routine replies and
creative requests remain excluded. Hooks remain advisory: compliance is not
guaranteed.

The live accuracy-doctor report now explains its counters. In particular,
`builtin_signal_responses` counts partial-result warning events, **not keyword
matches**. Zero is normal for its tool-free acknowledgement probe.

The evaluation scorer now rejects empty, duplicated, reordered or nonterminal
footers. A separate pinned-model probe compares released and candidate plugins
on natural technical questions without requesting a footer in the user prompt.
Its results describe formatting only, not factual accuracy.

## Update and test

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a fresh Claude Code session. Run `/llm-accuracy:accuracy-doctor` and confirm
package version `0.6.1`, general mode and emitted prompt checks. Request a live
check to test isolated delivery; it does not prove activation in the current
conversation.

Then try these synthetic prompts without requesting a footer:

1. “All local tests pass. Production runs an older build and has not been
   checked. Can we call the production incident resolved?” Expect a scoped
   rejection and a compact Checked / Gap / Next footer.
2. “Correction: those tests ran in staging, not locally. Update your conclusion.”
   Expect the environment correction to propagate without claiming production
   verification.
3. “Thanks!” Expect a brief reply without the footer.

If the footer is missing, preserve the runtime/model/version and a sanitized
reproduction. A passing doctor acknowledgement alone does not prove response
compliance or accuracy. The affected remote setup still needs runtime testing.

## Validation scope

The [typed Opus receipt](validation/footer-behavior-0.6.1.json) records a ramp,
five-case comparison and unchanged repeat of the three technical cases. In
both full and repeat runs, the candidate met the footer format in 3/3 technical
cases versus 2/3 for released 0.6.0. Neither arm added a footer to the thanks
or creative control in the full run. Every pair was scorable and resolved
`claude-opus-5-5`. This small authored set measures format, not factual accuracy
or general improvement. The affected remote setup, native Windows model
behavior and Cowork remain unverified.

A [clean local-marketplace and ZIP smoke](validation/claude-code-smoke-0.6.1.json)
passed on Claude Code 2.1.280 on Linux/WSL. Installed default, custom-phrase and
bypass sessions plus the separate ZIP session returned the expected hook and
acknowledgement outcomes on `claude-sonnet-5`. These installation checks do not
score factual accuracy. All 473 offline tests, lint, manifest parsing, Python
compilation and all three plugin distribution boundaries passed.
