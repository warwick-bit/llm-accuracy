# Data Execution local review

No unresolved blocking defect found in the reviewed local pilot scope. This is
not a release, live-provider correctness, native-MCP interception or model-token
saving verdict.

Independent Claude design and diff reviews completed. The parent verified the
findings locally: the missing validation narrative now exists; corruption's
store-wide capture blocking is explicitly documented and regression-tested.
The design review prompted removal of stdin capture because a downstream pipe
cannot establish producer success. Hash coverage, duplicate-key parsing and
partial-detail qualifications are enforced in the implementation.

A local correctness and silent-failure pass traced staged input through adapter
validation, immutable publication, fresh-process reads, expiry and deletion.
Unexpected errors return bounded codes; missing records and partial totals do
not become zeros. No provider adapters or production data were used.

## Quality Scorecard

Rubric: repository pytest, Ruff, manifest parsing, Python compilation and
plugin distribution boundaries. No CLEAN_CODE.md or function-size limit exists
in this checkout.

- Function length: AST inspection found a maximum of 46 lines in the new
  experiment's `run_case`; new runtime maxima are 27 lines (`adapter`, `save`)
  and 20 lines (`query`). Over-limit status is not applicable: no repo limit.
- Duplicate-block delta: not measured; no clone-count tooling was run.
- Type-coverage delta: not measured; new runtime functions are unannotated and
  no type-checker gate is configured for them. No strict-mypy pilot was run.
- Complexity delta: numerical delta not measured; Ruff C901 passes for all
  touched Python production/experiment files.
- Per-file: `data_contract.py` PASS — explicit parsing and exact arithmetic
  tested; `snapshot_store.py` WATCH — lifecycle tested, deliberate corruption
  blocking and same-user/plaintext boundary; `local_data.py` PASS — bounded
  receipts, selected retrieval and safe errors tested; `eval_data_execution.py`
  PASS — independent integer oracle, fresh-process retrieval and adverse cases;
  `check_distribution_boundary.py` PASS — new profile retains existing
  subprocess/network exclusions. Marketplace/manifests and release-gate YAML
  WATCH — local installation and parsing passed; CI is recorded on the PR.

## Compact proof

```text
proof:exact-calculation=proved; evidence=tests/test_data_execution.py; caveat=declared adapter semantics and source completeness are not independently certified
proof:durable-followup=proved; evidence=scripts/eval_data_execution.py; caveat=fresh-process recovery on tested local filesystem, not power-loss or backup recovery
proof:retention=proved; evidence=tests/test_data_execution.py; caveat=expired reads blocked, physical removal on capture/purge only
proof:context-saving=proved; evidence=docs/validation/data-execution-synthetic.json; caveat=selected synthetic output-byte comparison only; no native-token or existing-optimized-workflow lift claim
proof:host-install=proved; evidence=docs/validation/data-execution-install.json; caveat=isolated local installation, not model skill execution
```

## Native pilot follow-up review

The native pilot report was independently reviewed by Claude: no blocking finding
in the report's inference/measurement boundaries. That reviewer received the report,
not source receipts; the parent checked the receipts and ratios separately.
Local correctness and silent-failure review covered activation instructions,
format guidance and retained failure reporting. No runtime Python changed.
The unresolved partial-output contract failure prevents promotion.

### Quality Scorecard follow-up

The original PR scorecard above remains the runtime-code measurement. This
follow-up changes documentation, skill guidance and a raw-free evidence receipt.
Function-size delta: no Python functions touched in this follow-up. Duplicate-block,
type-coverage and numerical complexity deltas: not measured; no corresponding
measurement tool was run for this documentation-only follow-up.

- `plugins/data-execution/README.md`: PASS — enable step matches isolated activation probe.
- `plugins/data-execution/skills/local-data/SKILL.md`: WATCH — explicit format guidance remains advisory; partial-source output still fails strict formatting.
- `docs/INSTALL.md`: PASS — explicit opt-in activation documented.
- Validation reports/receipt: WATCH — single-observation synthetic host evidence, failures retained, local exploratory harness is not distributed.

Local validation: 617 pytest tests passed, Ruff passed, five manifests parsed,
eight hook modules compiled, Data Execution distribution boundary and diff whitespace
check passed. These checks do not override the failing model-output contract.

```text
proof:native-selective-comparison=proved; evidence=docs/validation/data-execution-native.json large-v3; caveat=one observation per arm, before format clarification, cached tokens included
proof:strict-model-output=missing; evidence=docs/validation/data-execution-native.json partial-v4; caveat=embedded values exact does not satisfy JSON-only output contract
proof:activation-instructions=proved; evidence=docs/validation/data-execution-native.json activation; caveat=isolated session activation, no live user installation
```

## Everyday automatic investigation

The new report and sanitized receipt preserve the no-go decision and all failed
host attempts. No production hook or Python changes are included in this follow-up.
The local experimental hook is intentionally not distributed or registered.

### Quality Scorecard — investigation follow-up

- Function-length distribution: no production function changes in this follow-up; original PR AST measurements remain above.
- Duplicate-block delta: not measured; no clone tool run for documentation.
- Type-coverage delta: not measured; no typed surface changed.
- Complexity delta: not measured; no production code changed.
- Per-file: no new production file touched. Validation report/receipt WATCH — bounded synthetic probes and transcript-visible applicability, not population token savings.

```text
proof:automatic-interception=proved; evidence=docs/validation/data-execution-automatic.json; caveat=isolated Bash/MCP text probes, not every tool or installed-hook coexistence
proof:everyday-token-benefit=missing; evidence=docs/data-execution-automatic-validation.md; caveat=medium offload increases usage; table-heavy Bash benefit is a favorable stratum and MCP table comparison is incomplete
proof:universal-source-fidelity=missing; evidence=large-boundary-probe in docs/validation/data-execution-automatic.json; caveat=host may truncate before hook; corrected candidate skips native persisted outputs
```
