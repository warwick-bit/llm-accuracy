# Accuracy 0.8.1 candidate (unreleased)

The candidate adds bounded numerical verification guidance and worked examples,
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

The [current compatibility receipt](validation/compatibility-candidate.json)
records the Windows-with-Git-Bash live bundle pass. The
[Accuracy installation and archive receipt](validation/claude-code-smoke-0.8.1.json)
records exact installed source matching and four bounded Sonnet 5.5 sessions.
These establish installation and hook delivery, not a general accuracy benefit.
An isolated native Codex skills-only installation also matched all 31 package
files; its manifest declares three skills and disables automatic hooks.

Publication remains blocked pending all four native installation CI receipts
from the same hosted run. Local Windows evidence cannot certify Linux, macOS or
a Windows host without Bash. Desktop Chat, Desktop Code UI and Cowork delivery
remain unverified. See the [compatibility contract](COMPATIBILITY.md). No normal
profile rollout or public release is included in this local qualification.
