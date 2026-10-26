# Accuracy 0.8.1

_Reached the main marketplace branch on 25 October 2026
([`2c994a3`](https://github.com/warwick-bit/llm-accuracy/commit/2c994a30c0b9237926b708c8f6d6d4570b51bb10));
the version tag and GitHub release remain pending as checked on 26 October 2026._

[PR #77](https://github.com/warwick-bit/llm-accuracy/pull/77) merged at
11:41 UTC on 25 October. Main delivers marketplace installs, so 0.8.1 is
available through that channel. No `v0.8.1` tag or GitHub release exists yet;
at that checkpoint the latest downloadable release was
[0.8.0](https://github.com/warwick-bit/llm-accuracy/releases/tag/v0.8.0), with
its ZIP and checksum. See the [release procedure](../CONTRIBUTING.md#releasing)
for publishing the 0.8.1 ZIP from its merge commit.

This version adds bounded numerical verification guidance and worked examples,
including the distinction between an executed check and a formal proof. It keeps
metric definitions and material assumptions visible across follow-ups and final
summaries. These instructions do not guarantee factual accuracy or prevention of
every failure. Background diagnostic and qualification processes launch without
a Windows console window.

Local qualification on 25 October 2026 used native Windows, Python 3.13.1 and an
isolated, checksum-verified Claude Code 2.1.287. The shared 2.1.281 CLI lacks the
required plugin configuration command and was not changed. The existing suite
passed with **1,215 passed, 31 skipped and zero failures**; skips identify POSIX
behavior or unavailable symlink privileges. The mandatory native hook no-skip
check, lint, manifest parsing, hook compilation and distribution checks passed.

The [compatibility receipt committed with this version](https://github.com/warwick-bit/llm-accuracy/blob/2c994a30c0b9237926b708c8f6d6d4570b51bb10/docs/validation/compatibility-candidate.json)
records the Windows-with-Git-Bash live bundle pass. The
[Accuracy installation and archive receipt](https://github.com/warwick-bit/llm-accuracy/blob/2c994a30c0b9237926b708c8f6d6d4570b51bb10/docs/validation/claude-code-smoke-0.8.1.json)
records exact installed source matching and four bounded Sonnet 5.5 sessions.
These establish installation and hook delivery, not a general accuracy benefit.
An isolated native Codex skills-only installation also matched all 31 package
files; its manifest declares three skills and disables automatic hooks.

At that local qualification checkpoint, publication still required all four
native installation CI receipts from the same hosted run. Subsequently,
[PR #77's Release Gates run](https://github.com/warwick-bit/llm-accuracy/actions/runs/40188895016)
passed all 17 checks, including installed Code on Linux, macOS and Windows with
and without Git Bash, marketplace publication and the required `release-gates`
aggregate. These hosted installation checks do not establish live model-session
delivery on those other hosts. Desktop Chat, Desktop Code UI and Cowork delivery
remain unverified. See the [compatibility contract](COMPATIBILITY.md). The local
qualification did not include a normal profile rollout or a tagged public release.
