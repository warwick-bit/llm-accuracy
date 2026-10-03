# Evidence Memory 0.5.0

Claude hooks now execute the configured Python interpreter directly. Native
Windows can run without Git Bash; Linux, WSL and macOS use the same argument
vectors. Python 3.9+ and Claude Code 2.1.287+ are required. Configure a working
Python executable in the plugin's `/config` entry before reloading or starting
a new session. Existing installations also need that explicit setting.

Ordinary session-lock overlap defers capture quietly and leaves the cursor
unchanged. A later hook catches up without duplicating events. Restore and final
capture wait for a bounded interval, then report a retry advisory if still busy;
real I/O errors remain visible. An interrupted final capture may need explicit
`sync`. Never remove a lock file to bypass a process holding it.

The question-answer capture introduced in [0.4.0](release-evidence-memory-0.4.0.md)
is preserved, including its local-only privacy disclosure and replay limits.
The separate Codex package remains experimental and requires a POSIX hook shell.

[Current compatibility evidence](validation/compatibility-candidate.json) binds
package bytes and keeps untested live/UI targets explicit. Publication requires
four real native credential-free installation/direct synthetic hook checks and
at least one genuine package-bound local live Claude Code pass. Direct synthetic
capture/retrieval is separate from model-driven capture and Desktop UI delivery.
See the [bundle release note](release-platform-candidate.md) and
[installed QA procedure](INSTALLED_QA.md).

This release improves hook portability and contention handling; it does not
establish an accuracy rate or guarantee factual correctness.
