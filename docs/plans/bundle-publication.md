# Optional bundle publication experiment

Desired outcome: a failed refresh must not expose new numerical data beside an
old report through the supported reader. Reduce the need to check for mixed
exports; no accuracy or speed improvement is presumed.

Smallest useful deliverable: an explicitly invoked, standard-library Python
producer/publisher/reader demo, fictional invoice inputs, consumer regressions,
and one independent review. This lives under `scripts/`, outside all plugin
packages. There are no hooks, installations, profile changes or solver dependency.

Essential checks: original and changed inputs read from another process;
all-cancelled and populated zero/credit outcomes; producer failure after staging
numbers and an exception after publication; direct-write and unpinned-reader
negative controls; invalid bindings rejected; valid row reorder accepted; exact
saved-byte hashes; required repository checks and independent review.

## Contract and boundary

`publication_demo.py refresh` is the producer. It consumes one JSON snapshot of
fictional AUD invoices, sums issued integer-cent amounts by customer, and produces
`summary.json` plus `report.csv`. The report is a labelled customer/AUD table,
not financial narrative. Validation compares the actual staged table with the
summary, including customer identities and exact amounts, independent of row order.
It is not an independent financial reference. Tests also assert hand-derived
expected results for the small fixtures.

The publisher reuses the completed pilot's design: fresh immutable generation,
staged-byte validation, hash manifest, atomic replacement of one reference.
The existing `os.replace` primitive is sufficient; no transaction framework is
needed. The `read` command pins that reference once and returns both documents
only after hash verification. Before the switch failure leaves the old generation;
after the switch an exception can leave the complete new generation. A first-run
failure may leave no current result, which the reader reports as an error.

Assumptions: one writer, local atomic reference replacement, immutable generations,
and no deletion of generations while readers may use them. Loose files and a
reader that resolves the current pointer separately for each file are outside the
contract. No power-loss/fsync durability, concurrent-writer, hostile-edit, network
filesystem or cross-platform guarantee is claimed. Failed staging directories
are retained for diagnosis; use a new disposable output root to repeat a demo.

## Failure lookback and preventive checks

| Observed failure | Preventive choice / named check | Residual gap |
|---|---|---|
| Partial refresh leaves mixed files | Stage producer outputs; `test_empty_producer_failure` and `test_invalid_candidate_and_post_switch_exception` | Application exceptions only |
| Readers bypass the contract | One pinned reader; `test_reader_pinning_and_bypass` | Cannot protect external loose-file readers |
| Consistently wrong documents | Hand-derived fixture assertions; `test_binding_variants` | Validator checks agreement, not authoritative sources |
| Stale policy prose passes a checker | CSV table only; explicit coverage in reader output and explanation | No narrative or causal claims checked |
| Legitimate row reorder rejected | Semantic keyed comparison; `test_binding_variants` | Only the declared CSV schema |
| Windows newline/hash mismatch | Byte serialization and hash actual saved files; `test_reader_pinning_and_bypass` | Hashes are integrity checks, not authentication |
| Abstract proof/reviewer PASS mistaken for protection | Separate-process CLI checks and defect controls | No formal refinement or installed-host efficacy |

## Prior proof and ownership

The completed pilot's model already checks eight UNSAT obligations with reachable
valid and faulty publication SAT controls. Its transitions/assumptions are not
changed here: writing the summary/table corresponds to its two document writes,
validation to its guard, reference replacement to publication, and exceptions
to abandonment or no further transition. UUID generation names stand for fresh
identities, not monotonic model integers. The model assumes a coherent initial
generation; a failed initial refresh has no previous result to fall back to.
File I/O, byte validation,
CSV parsing, business values and OS behavior are correspondence gaps, not modeled
proofs. Reuse the historical result; do not rerun or generalize it.

Ownership/disclosure review: source and fixtures in this candidate are newly
authored for the repository's MIT license. Only the general publication design
and lessons are reused; no private evaluation code, prompts, configurations,
actor artifacts, source data or provider payloads are copied. The CSV validator
is intentionally smaller than the pilot's private Markdown parser. Historical
proof receipts remain in the evaluation workspace and are not redistributed or
presented as fresh proof of this implementation.

## Try the actual consumer

Save this fictional input as `invoices.json` in a disposable working directory:

```json
{"invoices": [
  {"customer": "C-10", "cents": 10000, "status": "issued"},
  {"customer": "C-20", "cents": 4500, "status": "issued"}
]}
```

From the repository, using a working Python 3.9+ executable:

```text
python scripts/publication_demo.py refresh invoices.json demo-output
python scripts/publication_demo.py read demo-output
```

The reader returns both the numerical summary and CSV report with the same
`generation` identifier. Change an amount and refresh to see a new result. Change
both statuses to `cancelled` and run:

```text
python scripts/publication_demo.py refresh invoices.json demo-output --simulate-empty-report-failure
python scripts/publication_demo.py read demo-output
python scripts/publication_demo.py refresh invoices.json demo-output
python scripts/publication_demo.py read demo-output
```

The simulated report failure exits 1 after writing staged numbers. The next read
still shows the previous complete result. Refreshing without that simulation
publishes an empty summary and header-only report successfully. A nonzero refresh
exit does not always mean rollback: an error after the reference switch can leave
the new complete result. Always inspect using `read`; do not select loose files
from different directories. Keep output in the disposable root, outside plugin data.

## What a finance/data user can rely on

This protection concerns **publication consistency**: the supported reader gets
one complete generation. It also checks the narrow **output consistency** of
customer/value pairs. It does not establish **calculation correctness** beyond the
small examples, or **business/source correctness** (right population, definitions,
dates and authoritative inputs). An old complete report may be stale, and two
agreeing reports may both be wrong.

Side claims such as a growth percentage or “every customer improved” can be
checked only after their population, dates and meaning are specified. This demo
checks neither those claims nor causal explanations. No claim is made about
factual accuracy, time saved, live plugin delivery or model adoption.

## Scope discipline

Owner direction: keep this local for testing and iteration. Do not push branches,
open PRs, merge, release or install it.

Following the owner's simplicity reminder, this deliverable has one script and
five focused tests. The pilot's seven-boundary matrix and solver results are
reused as historical design evidence; no new boundary-injection interface,
framework, additional solver run or narrative checker is added. The only demo
failure switch reproduces the observed empty-data producer failure. The existing
repository suite is run as required, without expanding its unrelated coverage.

## Delivery evidence

The five focused consumer tests pass on native Windows / Python 3.13.1.
A retained separate-process demonstration also passed original, changed-input,
failed-empty-refresh and successful-empty-refresh assertions. Three successful
refresh commands took 355, 263 and 295 ms in that one local sequence, including
process startup; these are observations, not an estimate of isolated publication
overhead or a speedup. Exact script/test hashes accompany the local receipt.

Compatibility validation passes. All seven marketplace/plugin manifests parse,
and all 15 hook modules plus the demo compile. Repository-wide Ruff validation passes.
Independent read-only GPT-6.1 Sol review found no blocking defects, using the
complete three-file candidate and consumer receipt. It did not independently
execute the code, and explicitly left full-suite completion pending. The
repository-wide suite completed: 1,201 passed, 22 failed and 15 skipped (530.56 s).
All 22 failing test IDs also failed on unchanged base `402947b` in a separate
isolated checkout (11.97 s). These pre-existing Windows permission, path and hook
probe failures remain unresolved; the full suite is not green. The five new
consumer tests passed. No unrelated source was changed to repair the base suite.
The first full-suite attempt was interrupted after repeated shell setup failures: an inherited Bash
selection conflicted with PowerShell test prefixes. The rerun uses the repository
CI's explicit Git Bash test setting; no repository code changed for that issue.

The protected-source publication preflight reports four missing installed-host
receipts: Linux, macOS, Windows with Bash and Windows without Bash. No release
readiness is claimed and no installations were added to fill these gaps. Only
Python 3.13.1 on native Windows was exercised locally; other runtimes are untested.

The failure mapping above was checked against these results: the direct-write
control exposed the intended mixed output; the staged producer preserved the old
result; a post-switch exception left the complete new result; valid alternatives
passed. The remaining correspondence/source/prose gaps are unchanged. No newly
verified omission in the candidate requires another component or review pass.

This candidate is for local evaluation; any future merge of its script still requires the
repository's protected-source publication gates. Offline demo results do not
certify plugin installation, live delivery, or other OS/client support.

## Next local experiment: numerical commentary

Desired outcome: catch a wrong or stale numerical sentence even when its report
generator repeats it consistently. The owner authorizes autonomous local iteration;
all earlier no-push/no-PR/no-merge/no-install boundaries remain in force.

Smallest useful deliverable: one standalone checker for two explicit sentence
forms, using one supplied revenue snapshot and a text file with one claim per
line. It checks total growth and whether revenue increased for every declared
region. Every nonblank line is retained, including unsupported or compound prose.
No model call, automatic extraction, broad prose parser, plugin packaging,
publication refactor or new solver model is needed. Existing receipt validators
only establish structural evidence hygiene and cannot perform these calculations.

Essential checks: run the CLI on original and changed sources; distinguish a
wrong claim from missing evidence; accept legitimate rounding and presentation
variants; expose a false universal claim despite correct aggregate growth; never
certify unsupported/causal prose or an empty population. Use hand-calculated
fictional expectations, a small focused test file and one independent review.
Run required repository checks, reusing the recorded unchanged-base diagnosis
for the 22 existing Windows failures unless new blocking evidence appears.

Contract choices from the failure lookback:

| Failure | Choice and check | Remaining gap |
|---|---|---|
| Stale sentence agrees with its generator | Recalculate from supplied source; changed-source CLI check | Source authority still assumed |
| Prose-to-formal translation changes meaning | Recognize two complete sentence forms; preserve sentence and expose interpretation | Other wording is not verified; no extraction efficacy claim |
| Selected correct claims imply whole-answer approval | Retain every nonblank line and per-line outcome; no overall truth/pass flag | One claim per line is the supported input contract |
| Wrong population or dates | Match exact declared regions, currency and distinct ordered periods | Declared population may itself omit real-world regions |
| Missing evidence treated as false or true | Separate not-verified from contradicted; incomplete/empty population controls | Cannot recover missing evidence |
| Valid alternatives rejected | Source/claim reordering, case/whitespace and declared display-precision checks | Only two sentence forms, not arbitrary paraphrases |
| Check receipt goes stale or hashes wrong bytes | Hash exact source, report and checker bytes in each result | Historical results remain historical; no automatic invalidation service |

Only the numerical value of an increase is checked; an increase is not called an
improvement in business performance. Growth requires a positive starting total;
zero/negative denominators need another agreed definition and remain unverified.
Percentages are rounded to the sentence's displayed precision (zero to two decimal
places), with ties away from zero. Integer-cent input and exact integer arithmetic
avoid floating-point tolerances. A supplied population and revenue definition are
assumptions, not independently verified facts.

Run the fictional example from the repository root:

```text
python scripts/numerical_claims_demo.py tests/fixtures/numerical-claims/source.json tests/fixtures/numerical-claims/claims.txt
```

The supplied revenue totals are AUD 3,000 and AUD 3,360. The result supports the
12% sentence, contradicts 15%, supports an increase in both declared regions,
and leaves the causal sentence and compound numerical/audit sentence unverified.
The five input lines remain visible. Copy the fixtures to a disposable directory
to experiment; changing September South revenue to 207000 cents gives 9% total
growth, and the unchanged 12% sentence is then contradicted.

Supported forms (case, whitespace, optional final period and displayed numerical
precision may vary):

- `Total revenue growth was 12% from 2026-08 to 2026-09 in AUD.`
- `Revenue increased for every region from 2026-08 to 2026-09 in AUD.`

The source defines `metric: revenue`, one `currency`, a nonempty unique
`population` list of regions, and `values_cents` mapping each selected YYYY-MM to
exactly those regions and signed integer-cent amounts. A missing region, wrong
currency, missing period or undefined growth denominator yields not verified.
Duplicate JSON keys produce an execution error instead of silently selecting one
value. The consumer must inspect per-line statuses: CLI exit 0 means execution
completed, not that the claims are true. Exit 2 means input/execution failure.

The checker does not understand arbitrary paraphrases. For example, an unfamiliar
wording can be factually correct and still return not verified. Each report line
must be a complete claim; unsupported paragraphs/compound claims remain visible
without partially certifying a recognized fragment. The result exposes the
interpreted periods, currency, declared population, arithmetic and counterexamples.
This is an explicit local workflow, not an install-and-forget Claude plugin.

Five new focused tests and the five existing publication tests pass together
(10 passed). The changed-source control establishes that repeating the original
sentence does not make it pass; the checker consumes changed data independently.
Five retained separate-process scenarios also pass: original mixed claims,
changed source with old report, corrected numerical claim, aggregate growth with
one declining region, and missing region. The last two distinguish contradicted
from not verified. Exact input/checker hashes bind each result. Compatibility,
repository-wide Ruff, all seven manifest parses and all 15 hook compilations plus
the new checker pass. Independent read-only GPT-6.1 Sol review found no blockers
in the complete bounded packet. It did not independently execute the code or
verify the hashes. The full native Windows suite completed with 1,206 passed,
22 failed and 15 skipped in 735.18 seconds. Its 22 failed IDs exactly match the
previously reproduced unchanged-base failures; there are no additional failures.
JUnit confirms all five new tests and all five publication tests passed without
skips. The full suite remains non-green due to those existing gaps; no unrelated
fixes or additional review pass were added. Current checker, tests and fixture
hashes still match the retained consumer/reviewer packet.

The failure mapping above is satisfied within the declared scope. In particular,
the original 12% sentence becomes contradicted after the source changes, missing
regional evidence remains not verified, and a valid reformatted/rounded claim can
pass. Unverified prose and source authority remain visible gaps. No new blocking
omission requires expanding the framework. No general accuracy or time-saving
estimate is claimed. All work stays local for further experiments.
