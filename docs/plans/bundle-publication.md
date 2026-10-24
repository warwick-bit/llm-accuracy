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

## Prompted model-use qualification

Desired outcome: establish whether a model actually uses the unchanged numerical
checker, corrects contradicted claims and communicates unsupported claims honestly.
The owner authorized this local experiment after reviewing the parallel session's
completed ordinary-versus-recurring-check comparison. Reuse that evidence; do not
duplicate its campaign or its ongoing stale-policy checker work.

Smallest useful deliverable: one isolated Sol 6.1/high session, three deliveries
(new fictional report, changed source, incomplete source), saved actual commands,
checker results and reader-facing dispositions. Reuse the established isolated
native CLI transport and snapshot runner. No product/runtime changes, plugin,
new parser, new repository test group or general efficacy comparison. Claude
coverage remains unavailable on the previously qualified route; do not substitute
this Sol run for Claude evidence. Explicit prompting tests assisted adoption,
not spontaneous invocation. The existing 64k setting is retained without trying
to induce compaction or estimate a session-length threshold.

Essential checks: freeze inputs/checker/runtime and hand-derived expectations
before the first call; verify source/checker preservation and actual execution;
independently rerun saved checker inputs; inspect every original claim and all
final prose; verify source changes invalidate earlier arithmetic and missing data
stays unknown. Retain failed attempts and overhead. One independent delivery
review covers these results. Reuse prior repository checks because executable
repository source is unchanged; only this existing brief changes.

Failure mapping: a claimed check is not execution -> inspect native tool receipts
and saved byte bindings; correct totals hide false universals -> include aggregate
growth with a declining region; lexical checks reject valid wording -> include a
supported format variant and a true unsupported paraphrase; partial checking
overclaims truth -> retain causal/compound claims and distinguish unchecked from
false; stale receipts -> deliver a changed snapshot then incomplete data. Residual
gaps: one synthetic trajectory, same-family author/auditor, no expert gold, no
matched Claude run, no unprompted adoption, no repeatability or efficacy estimate.

Collection completed with three deliveries in the same Sol session, eight actual
checker executions, no observed compaction and no source/helper/prior-output
mutation. Original growth was 25%, became 15% after a source correction, then
became unknown when one region was missing. The model propagated those changes,
preserved the legitimate formatting variant, independently checked an unfamiliar
paraphrase and kept causal/customer-audit claims unresolved. Parent inspection
found no material delivered error within the declared scope. Eight saved results
reproduce as identical parsed JSON; all 34 frozen pins matched after collection.

The model also independently calculated its corrections in the same tool command
that executed the helper; no distinct model repair turn driven by checker feedback
was established. This is prompted-use qualification, not causal accuracy benefit.
Native stage-call time totals 136.405 seconds; it is neither isolated checker
overhead nor total evaluation cost. Detailed synthetic prompts, outputs and
receipts stay outside repository source. The only repository change is this
brief; prior source checks are reused.

Independent Sol 6.1/high delivery review returned no blockers. The initial packet
hit the review wrapper's 80,000-byte default and omitted later consumer outputs;
its PASS was retained with that limitation. A targeted 70,374-byte supplement
delivered the missing second/third outputs and complete brief diff without
truncation or redaction, confirmed by dry-run and actual metadata. Its PASS/no
findings explicitly closes that missing-output coverage. Both reviews were
packet-only, not independent executions or hash checks. No actor run was repeated.
The owning packet workflow now records the necessary pre-call byte/coverage check;
no shared wrapper or new test framework was changed. Essential checks and bounded
review are complete; stop this trial without extra features or collection.

## Larger mission: reusable local verification workflow

Owner now requests a larger autonomous session goal, explicitly superseding the
one-trial stop boundary above. Desired outcome: dependable everyday financial/data
outputs with less bespoke prompting and manual checking. A useful result must
show actual consumer use, honest coverage and acceptable effort; it need not add
code or prove general efficacy.

Smallest useful deliverable: a short reusable optional workflow around the existing
checker, qualified on ordinary source files and naturally worded reports. Begin
with one review-and-source-update trajectory using CSV input, then an independent
fresh task that produces a report. Use only a few necessary deliveries. Record
claims that require model interpretation or independent arithmetic; do not expand
the regular expressions to manufacture coverage. A normal workflow document is
sufficient unless real consumer evidence justifies skill/plugin packaging. No
installation or live-profile change is authorized. Existing publication mechanics
stay separate unless a tested consumer actually needs bundled publication.

Essential checks: before collection freeze the workflow, checker, inputs, runtime
and hand-derived expectations; preserve original raw sources and claims; inspect
the model's conversion from raw data to checker input and from prose to checked
statement; distinguish execution, partial coverage, source binding and unsupported
claims; exercise source updates and legitimate alternatives. Keep complete failed
attempts and timings. Fix only verified consequential gaps, rerun only affected
behavior with fresh cases where relevant, then independently review the final
deliverable. Review packet delivery must pass its byte/redaction dry-run check.
Reuse established code tests when source is unchanged.

Failure mapping: a correct derived JSON can hide wrong raw-source mapping -> audit
actual row population/units/periods against original files; canonical text can
reject true variants -> retain original prose and explicitly map meaning without
claiming the parser verified it; narrow checks can mask side claims -> inspect the
whole reader-facing report and list meaningful unchecked conclusions; stale input
bindings -> raw and derived source identities and a changed-source continuation;
review truncation -> preflight delivered byte coverage. Same-family authorship,
few synthetic trajectories and absent matched Claude access remain gaps, not
reasons for a broader campaign. No global hooks, proof engine or universal schema.

The verification session owns this workflow and its focused consumer trials.
The other session retains broad model comparisons and its completed private
stale-policy check. Communicate through the existing mutually acknowledged notes;
do not modify its checkout, shared frozen runners or receipts. Local-only/no-push,
PR, merge, release, install or paid API boundaries remain. Continue autonomously
through the above stages; stop at a reviewed useful candidate or concrete limit,
not after each setup step. Ask only for a consequential unresolved owner decision.

Owner subsequently authorizes limited Opus 5.5/Sonnet 5.5 subscription evaluations
after Sol 6.1 iteration, and Sol 6.1 subagents for useful concurrent work. Native
Claude's current Team login was explicitly confirmed by the owner as intended.
The evaluation session owns matched Claude calls and capacity accounting; this
session supplies the stable workflow and focused comparison request, avoiding
duplicate calls. No paid API fallback. Two read-only Sol subagent tasks cover
fixture/source interpretation and safe runtime preparation.

First workflow qualification: two Sol deliveries using raw CSV and a naturally
worded report correctly propagated 15%/AUD23,000 to 5%/AUD21,000, preserved valid
wording, rejected a false universal increase and retained causal uncertainty.
Five helper outputs reproduce, raw-to-derived values match, inputs/prior outputs
are unchanged and all 37 pins matched before iteration. Independent source audit
agrees. A concrete usability defect remains in the actor's evidence: reproduction
commands said "from this directory" but required the parent work root. A controlled
run from the delivery directory failed for that missing path, while the same inputs
reproduced from the correct root. The owning workflow now requires an explicit
working directory. The next fresh generation task checks that small correction
as well as signed revenue and an undefined percentage from a zero baseline.

The fresh generation task correctly kept legitimate negative credits, reported
AUD0 to AUD100 total change, and left total/negative-baseline percentage growth
undefined under the supplied definitions. Both regions increased AUD50; Harbour's
positive-baseline growth was 50%. The helper supported the every-region sentence;
six other paragraphs required separate interpretation/arithmetic. All 37 pins,
12 recorded manifest hashes and raw-to-derived values matched. A disposable WSL
replay reproduced the report, claims, calculations and full helper JSON while
preserving original evidence. The explicit working directory was correct.

Two evidence limitations remain visible: the actor's audit says its script
regenerates the audit, but it only retains/hashes that separately authored text;
and replay under Windows changes generated line endings and thus source/claim
hashes despite equivalent calculations. The original-host WSL replay matches.
Neither artifact is a general report generator. These private consumer artifacts
are retained unchanged; no production code or new regression groups are warranted.

The smallest useful deliverable is the optional workflow document, not plugin
packaging. It reduces the bespoke instructions supplied in these tasks but still
relies on an assistant to interpret raw sources and unsupported prose. Three
deliveries across two Sol sessions do not establish repeatability, net time saved,
or accuracy improvement over an untreated assistant. No compactions occurred.
Independent source inspection found no material numerical/report-content error;
the separate final delivery review remains required. Prior implementation tests
are reused because helper/publication source is unchanged, including the disclosed
22 pre-existing Windows suite failures. No full-green or release-readiness claim.

The other session has qualified restored WSL subscription access and owns its
limited CFO Opus/Sonnet collection. A frozen v2 workflow comparison request was
handed off for one initial report-review task per Claude model only if its existing
native-tool route and capacity permit. Acceptance/results remain pending; this
session has made no Claude inference call. The initial Sol reference used v1
(before the cwd sentence), so any comparison must disclose that prompt difference.

Final independent Sol 6.1/high personal delivery review returned PASS with no
findings. Dry-run and actual metadata both confirm 121,725 evidence bytes with
no truncation or redaction. This was a packet-only review; execution/preservation
conclusions rely on parent audits and supplied artifacts. The review explicitly
retains the reproduction limits, three-delivery synthetic scope, absent Claude
results and pre-existing suite failures. Current diff whitespace and compatibility
checks pass. The bounded workflow deliverable and essential checks are complete;
do not add packaging, parser capabilities or more Sol cases without new evidence.
The separately owned Claude comparison request remains a handoff, not a completed
comparison or a reason to hold this useful local checkpoint open indefinitely.
