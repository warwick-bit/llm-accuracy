# LLM Accuracy 0.6.5

This patch adds one check to `/llm-accuracy:self-audit`. When an audited answer
reconciles sources that disagree and the data does not say which source is
official, the answer must name the source the governing rule or
source-of-truth registry picks and state that basis. The audit now treats
"the data can't establish which is official" as a correction, and naming the
other source as wrong. The rule must be checkable (a registry entry, a
documented definition, or the user), never taken from the audited answer;
without one, the answer should say official status is unconfirmed. Hooks
and other skills are unchanged.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a new Claude Code session or run `/reload-plugins`, then confirm package
`0.6.5` in `/llm-accuracy:accuracy-doctor`. ZIP users can use the
`llm-accuracy-0.6.5.zip` release asset. See the [install guide](INSTALL.md).

## Validation and limits

In a private reviewer benchmark (six cases, one run each, screen-grade),
reviewers without this rule passed 4 of 6 answers that withheld the official
source. With the rule they caught 6 of 6. The rule alone did not stop one
model from accepting an answer's own wrong domain rule; giving the reviewer
a source-of-truth card listing each topic's official-source rule did. The
checkable-rule and "unconfirmed" clauses were added after that benchmark and
are untested. It improves one audit check; it does not guarantee a correct
answer.
