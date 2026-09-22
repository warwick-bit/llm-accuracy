# Research notes for the analytical reviewer

Reviewed on 23 September 2026 alongside the follow-up experiment. These sources motivate tests and
design choices; none establishes that this plugin beats current Claude.

## Current product and evaluation guidance

Anthropic's [agent-evaluation guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
emphasizes unambiguous reference tasks, balanced positive and negative examples,
isolated runs and calibration of model-based graders. This supports fixing the
missing-FX rubric and separating numeric correctness, coverage and explanations.
It does not make an author-built synthetic suite representative of a workplace.

Anthropic's [Code Review announcement](https://claude.com/blog/code-review)
describes a multi-agent PR-review product. Its public
[code-review command](https://github.com/anthropics/claude-code/blob/main/plugins/code-review/commands/code-review.md)
uses specialist review followed by validation of findings. The inspected command
also excludes some input/state-dependent issues to reduce noise. That boundary
is unsuitable as a blanket rule for analytical review: duplicate keys, NULLs,
date boundaries and event ordering are often exactly the inputs that expose a
material defect. Borrow independent validation, not every PR-specific filter.

## Executable checks and evidence

[Semantic Evaluation for Text-to-SQL with Distilled Test Suites](https://github.com/taoyds/test-suite-sql-eval)
evaluates behavior over test databases rather than relying on SQL text identity.
This motivates a fixture where two incorrect order results cancel into a correct
total. One matching aggregate cannot prove the transformation is correct.
[SQLancer](https://github.com/sqlancer/sqlancer) uses test oracles to expose
database-engine bugs; it is useful methodological background, not a substitute
for reviewing a company's business definitions.

[FinQA](https://github.com/czyssrs/FinQA) includes supporting facts, reasoning
programs and execution answers for financial questions. Its repository also
documents a historical label-leakage bug. The lesson for this plugin is to keep
the answer key outside reviewer access and to inspect calculations and evidence
selection separately. We did not import its data, run its benchmark or claim its
published results as our own.

For the FX evidence-gap diagnostic, the IFRS Foundation's
[IAS 21 text, paragraphs 28–29](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/english/2024/issued/part-a/ias-21-the-effects-of-changes-in-foreign-exchange-rates.pdf?bypass=on)
distinguishes settlement from prior recognition/translation of a monetary item.
This supports checking the item's accounting basis before labeling a difference
between two supplied rates a realized gain. The synthetic packet's revenue
translation policy does not establish that basis. This source was consulted
after the first observed FX failures to check the interpretation; neither the
frozen fixture nor its reference answer was changed. The fixture is not an
IFRS-compliance test or advice about a real company's accounting.

[Knossos](https://github.com/jepsen-io/knossos) checks operation histories against
a sequential model and distinguishes completed, failed and uncertain operations.
This motivates an explicit event trace and a correct CAS retry control. A
generic warning about concurrency should not override the supplied atomicity and
failure semantics. Our small simulation is not a Knossos or production Jepsen run.

## What self-correction research does and does not imply

[CRITIC](https://arxiv.org/abs/2305.11738), with
[public code](https://github.com/microsoft/ProphetNet/tree/master/CRITIC), studies
correction using feedback from external tools. It motivates verification through
calculators, query execution and source retrieval rather than model agreement.
Its evaluated models/tasks differ from this Claude setup; its reported gains do
not transfer automatically.

[Chain-of-Verification](https://arxiv.org/abs/2309.11495) separates verification
questions from the initial response to reduce answer contamination.
[Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798)
reports limitations of correction without external feedback on its tested
reasoning tasks. These older findings are reasons to test freshness and feedback,
not timeless claims about all current models.

[Self-Correction Bench](https://arxiv.org/abs/2507.02778) studies a distinction
between correcting one's own output and identical externally presented errors;
its reported population is open-source non-reasoning models, not this Claude
configuration. The newer
[financial QA compilation preprint](https://arxiv.org/abs/2605.31064) combines
training and executable reasoning programs. That is a materially different
intervention from adding a reviewer prompt. Neither supports asserting that a
generic Claude skill inherits the paper's measured improvement.

## Working inference

The portable part is a review workflow that obtains the relevant artifacts,
preserves their definitions and checks material claims against executable or
source-grounded evidence. Whether extra instructions, a second agent, a different
model or a review council add enough value is a separate empirical question.
The follow-up comparison keeps tools, context freshness and output contract
equal so it can isolate the candidate prompt's incremental effect within that
bounded setup. It cannot isolate the benefit of freshness or tool access itself.
