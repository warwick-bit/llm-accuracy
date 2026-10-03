# Automatic Python discovery — patch candidate

LLM Accuracy 0.7.1, Session Ledger 0.3.1 and Evidence Memory 0.5.1 remove the
required Python setting introduced by the portability release. Existing users
with no setting and new installations automatically probe `python3`, `python`,
then Windows `py -3`, and run the hook once with the first working Python 3.9+.
Store aliases and old interpreters are skipped. No Git Bash or Node installation
is required on native Windows. Python itself remains a prerequisite.

Saved executable overrides survive upgrades and take precedence. An invalid
saved override produces an advisory: correct or clear it in `/config`.
Missing Python produces the same advice without blocking a turn. Option values
are never parsed as shell commands. The batch/POSIX dispatcher uses the platform
shell and invokes Python directly from the batch section on native Windows. Evidence Memory's
separate experimental Codex POSIX launcher is unchanged and version-aligned.

A manifest `default: python3` alone was tested and rejected: the installed host
did not execute hooks for unset options. This patch performs discovery inside
the launcher and removes the dependency on host default substitution.

Validation is pending. The [compatibility matrix](validation/compatibility-candidate.json)
remains package-bound. Native installation and direct hook execution are required
on Linux, macOS and Windows with and without Bash. Local live QA must also
prove delivery after an unset-option upgrade. Desktop, Cowork and live delivery
on other operating systems remain unverified. Hook delivery does not establish
factual accuracy.
