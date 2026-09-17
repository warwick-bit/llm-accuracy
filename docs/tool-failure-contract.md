# Tool failures, refreshes and evidence receipts

This is integration guidance for people building source adapters and answer
publishers. The public plugins remain advisory. Their bundled receipt validators
check structure and declared metadata; they do not inspect source values,
execute arithmetic, authenticate citations or intercept every answer.

## Validate before formatting

A successful transport response can still lack an input required by a metric.
An adapter should check the response shape, required fields, value types and
finite numeric values before formatting or calculating. Distinguish a missing
value from a valid zero. Do not coerce null to zero, truncate a fractional count,
or use a nearby field as a replacement. Validate dates and units against the
adapter's domain contract rather than assuming that nonempty text is valid.

Return a stable structured failure when those checks fail. For example,
`missing_input`, `invalid_input`, `source_unavailable` or `definition_mismatch`
can be adapter-owned codes; they are not new fields in the public receipt schema.
Use a fixed safe explanation and trusted field names, not a raw exception or
provider value. Record the failed attempt through the same host-owned outcome
path as successful reads. A tool exception before that path can leave no usable
evidence for the current request.

A refusal is an outcome, not a zero-valued answer. If the host cannot create or
bind an outcome, treat that as missing evidence, not a successful refusal test.

## Refresh means a new attempt

Keep each request's evidence bound to a host-issued epoch and source attempt.
A prior successful response does not authorise a current answer after refresh
fails. Supply the expected current epoch from the host, not from the proposed
receipt. The public validator can reject a mismatching epoch when its caller
supplies `--expected-epoch`; it does not create, authenticate or persist epochs.

An older observation may be shown only as explicitly historical, with its
original observation time and failed-refresh disclosure, when the application
allows that. A request for a fresh-only answer must withhold the figure. Changing
the receipt's epoch alone does not turn an old observation into fresh evidence.

## Keep the verification layers separate

- **Receipt structure:** required fields, declared statuses and caller-supplied epoch agreement.
- **Captured-value fidelity:** output fields match host-captured evidence.
- **Derived calculations:** expressions, units, scope and rounding are checked
  by a deterministic calculation engine.
- **Source validity:** data freshness, completeness and domain definitions have
  independent support.
- **Exploration:** hypotheses and recommendations remain explicitly uncertain.

Only the first layer is provided by the bundled receipt validator. Its result
labels that authority as `structural_only`. A model can
invent a structurally valid source identifier. A hash identifies captured bytes;
it does not prove those bytes are true. A well-formed report with workings can
still contain wrong arithmetic. An "unverified" label does not make invented
facts harmless, and checked fact cards do not certify nearby model prose.

An optional host-controlled publication boundary can render only validated
fields or release a captured paragraph. That requires separate implementation
and review; a model instruction or a receipt alone cannot enforce it. Test every
retry as a fresh proposed answer. Stop hooks and buffered consoles also differ:
a check after streaming cannot retract text the user has already seen.

## Regression matrix for adapter owners

Use fictional data and retain only safe outcome metadata in shared artifacts.

```text
Case                     Expected adapter/publication behaviour
Healthy inputs           Successful answer with bound evidence
Valid zero               Success; zero is not treated as missing
Missing required input   Structured failure; no computed figure
Invalid numeric input    Reject text, bool, non-finite or fractional count
Failed refresh           Current failure; no silent prior-value reuse
Source unavailable       Structured failure; no guessed substitute
Definition mismatch      Withhold the affected metric
Wrong arithmetic/source  Reject at the applicable deterministic boundary
Repeated invalid retry   Still rejected; retry flag grants no exception
Unchanged valid answer   Accepted positive control
```

The receipt fixtures in `tests/fixtures/tool_failure_receipts.json` cover only
metadata-level refusals, promotion attempts and epoch mismatch. They contain no
provider rows, amounts or query results. Observation timestamps are fixed
fictional values; the declared `current` status is not a wall-clock freshness
check. Run:

```bash
python3 -m pytest -q tests/test_tool_failure_receipts.py
```

The tests also include an intentionally invented source identifier that passes
structural validation. That is a limitation control, not a factual-accuracy
success. They do not test adapter numeric classification, real tool failures,
retry enforcement, streaming, or model behaviour; integration owners must add
those tests around their actual adapters and clients.

For model-in-loop tests, separate actual tool execution, fault injection and
publication replay. Compare the same captured run when measuring a publisher;
use a separate controlled experiment to compare agent behaviour. A forced bad
draft demonstrates checker behaviour, not spontaneous model fabrication.
Exact-text differences may be harmless formatting differences. Report no-tool,
ambiguous capture and incomplete runs separately instead of counting them as
safety wins. Small synthetic runs cannot establish a general hallucination-rate
improvement.

## Public-source review and lineage

This guide and its fixtures were authored as generic abstractions of adapter
failure investigations. No private transcript, provider response, business
number, source identifier, runtime path or implementation was copied. The
fixtures describe fictional receipt metadata only. Review changes for privacy
before publishing, including PR descriptions and test artifacts.

The deliberate downstream boundary is unchanged: adapter execution, persistent
host receipts and blocking publication enforcement remain application-owned.
These docs do not update packaged hooks or claim a new runtime protection.
