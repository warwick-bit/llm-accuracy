# Companion tools

These third-party open-source tools handle jobs that sit next to the LLM
Accuracy plugins. They are not part of the plugins, and this project does not
endorse them. Their authors have not reviewed or endorsed these plugins.

**Read this first.**

- **One-off check:** each tool was smoke-tested once, on 2 Oct 2026. We
  installed it into a clean virtual environment and ran its documented basic
  use on synthetic data. No model calls were made.
- **Not an accuracy claim:** we did not test whether any tool makes Claude's
  answers more accurate.
- **Licences change:** licences and repository details were read on 3 Oct
  2026. Re-check the licence and the latest release before you use a tool.
- **Your data:** try each tool on synthetic data first. Some tools write files
  that can contain real values from your data.

**Evidence labels.**

- **Smoke-tested:** installs and runs as documented on synthetic data.
- **Smoke-tested, with caveats:** installs and runs, but part of the
  documented use failed or was not run. The caveat says which part.
- **Reference only:** read, not run. Useful as a method or research reference.

## Value-level data diffs before and after a SQL change

Use these to compare a query's output before and after a change. A
"refactor" that silently changes values then shows up as a diff.

### [datacompy](https://github.com/capitalone/datacompy)

- **Licence:** Apache-2.0.
- **What it does:** compares two DataFrames (pandas, Polars, Spark or
  Snowpark) and reports which rows and values differ.
- **Checked on 2 Oct 2026:** version 1.1.0 installed and ran its documented
  comparison on synthetic data.
- **Evidence:** smoke-tested: installs and runs as documented on synthetic
  data.

### [reladiff](https://github.com/erezsh/reladiff)

- **Licence:** MIT. The licence file holds two MIT notices and has no title
  line, so GitHub does not detect it automatically.
- **What it does:** diffs tables in one database or across databases, running
  the comparison inside the database.
- **Checked on 2 Oct 2026:** version 0.6.0 with the DuckDB extra. It worked on
  DuckDB. It could not read SQLite. When it reported a difference ("2 rows
  updated"), the command still exited 0.
- **Caveat:** a script or CI step must read reladiff's output. The exit code
  alone does not show that differences were found.
- **Evidence:** smoke-tested, with caveats: DuckDB only in our check; the exit
  code does not signal differences.

## Doc-with-code co-change checks

### [ifttt-lint](https://github.com/simonepri/ifttt-lint)

- **Licence:** MIT.
- **What it does:** fails a check when a diff changes one side of a
  `LINT.IfChange` / `LINT.ThenChange` pair but not the other. An example is a
  SQL query and the doc that defines its metric.
- **Checked on 2 Oct 2026:** prebuilt binary v0.11.2, checksum verified. We
  linked a SQL block to a doc. A git range that changed only the SQL exited 1.
  A range that changed both exited 0. A separate re-run gave the same result.
- **Evidence:** smoke-tested: installs and runs as documented on synthetic
  data.

## LLM-judge error correction

### [judgy](https://github.com/ai-evals-course/judgy)

- **Licence:** MIT.
- **What it does:** estimates a system's true pass rate from LLM-judge labels.
  It corrects for the judge's measured true-positive and true-negative rates
  and adds a bootstrap confidence interval.
- **Checked on 2 Oct 2026:** version 0.1.0. With a true-positive rate of 0.9,
  a true-negative rate of 0.8 and an observed pass rate of 0.6, it returned
  0.571429. That matches the closed-form correction
  (0.6 + 0.8 − 1) / (0.9 + 0.8 − 1).
- **Note:** its README says the correction assumes the judge does better than
  chance (true-positive rate + true-negative rate > 1).
- **Evidence:** smoke-tested: installs and runs as documented on synthetic
  data.

## Replayable analysis notebooks

### [showboat](https://github.com/simonw/showboat)

- **Licence:** Apache-2.0.
- **What it does:** builds Markdown documents that mix notes, commands and
  their captured output. `showboat verify` re-runs the commands and checks
  that the output still matches.
- **Checked on 2 Oct 2026:** version 0.6.1. After we hand-edited a recorded
  output, `showboat verify` exited 1.
- **Evidence:** smoke-tested: installs and runs as documented on synthetic
  data.

## Database profiles an agent can read offline

### [dbprint](https://github.com/jakubro/dbprint)

- **Licence:** Apache-2.0.
- **What it does:** writes a text snapshot of a database's structure and
  column-level value distributions that you can commit to git. Agents read it
  offline. An optional read-only MCP server serves the snapshot.
- **Checked on 2 Oct 2026:** installed and profiled synthetic data. It needs
  Python 3.13 or later.
- **Caveat:** a snapshot contains real cell values and value sketches.
  Personal data ends up in the file unless you configure its redaction rules.
  Its `init` command writes `~/.dbprint/connections.yaml`.
- **Evidence:** smoke-tested: installs and runs as documented on synthetic
  data.

## Specification curve and multiverse reporting

### [specification_curve](https://github.com/aeturrell/specification_curve)

- **Licence:** MIT, declared in `pyproject.toml`. The repository has no
  LICENSE file.
- **What it does:** fits a model under many defensible specifications and
  charts how the estimated coefficient changes.
- **Checked on 2 Oct 2026:** PyPI release 0.3.9. We used synthetic data with a
  true effect of zero and one confounder. Fitting and plotting worked: 4 of 8
  specifications were falsely significant, and all 4 left out the confounder.
- **Caveat:** `fit_null` failed with `KeyError: 'p-val'` under pingouin 0.6 or
  later, which renamed that column. Pinning `pingouin==0.5.5` and `pandas<3`
  avoided the error. So did installing from the git main branch. On 3 Oct 2026,
  PyPI still listed 0.3.9.
- **Evidence:** smoke-tested, with caveats: `fit_null` fails on the PyPI
  release with current pingouin.

## Agent transcript review

### [Inspect Scout](https://github.com/meridianlabs-ai/inspect_scout)

- **Licence:** MIT.
- **What it does:** runs scanners over AI agent transcripts. It includes an
  importer for Claude Code session files.
- **Checked on 2 Oct 2026:** version 0.5.3 installed. Its Claude Code importer
  was run as a dry run only.
- **Caveat:** we did not run a scan, because the scans we would use need model
  calls.
- **Evidence:** smoke-tested, with caveats: install and importer dry run only.

## Reference only

We read these but did not run them. We do not suggest running them as
shipped.

### [AgenticBootstrap](https://github.com/jmiao24/AgenticBootstrap)

- **Licence:** MIT.
- **What it is:** runs a team of Claude agents, each with a different
  prior-belief persona, on one dataset and question. It shows how much a
  conclusion depends on analytical choices. The method comes from
  [The Agentic Garden of Forking Paths](https://arxiv.org/abs/2607.01507).
- **Safety caveats (code read on 3 Oct 2026):** agents run with
  `permissionMode: "bypassPermissions"`. They receive the full process
  environment, including any credentials in it. The sandbox is set with
  `failIfUnavailable: false`, so it runs unsandboxed when its sandbox tools are
  missing, instead of stopping.

### [llm-phacking](https://github.com/janetmalzahn/llm-phacking)

- **Licence:** MIT.
- **What it is:** the replication archive for Asher et al. (2026), "Do Claude
  Code and Codex P-Hack?". It holds 640 analysis runs, the prompts and four
  datasets from published papers.
- **Safety caveats (code read on 3 Oct 2026):** the runner scripts use
  `--dangerously-skip-permissions` (Claude Code) and
  `--dangerously-bypass-approvals-and-sandbox` (Codex). Without `-n`, the
  Claude runner defaults to 50 runs per prompt; the README example passes
  `-n 10`.
- **Data terms:** the datasets come from third-party papers. The repository's
  MIT licence may not cover them. Check each dataset's original terms.
