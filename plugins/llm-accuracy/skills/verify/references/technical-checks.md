# Technical checks

- Pin the affected process, environment, version and expected behavior. Keep local
  repair, local testing, installation, deployment and production verification distinct.
- Reproduce the symptom with the narrowest safe check, or inspect the actual
  evidence when reproduction is unavailable. Record that limit. Test the strongest
  competing causes with an observation that could distinguish them; do not infer
  a cause just because a retry, restart or unrelated probe succeeded.
- Inspect the owning component and consumers before changing it. A recovery
  recommendation also claims that the proposed action permits the blocked operation:
  inspect prerequisites and validation order and test the exact remedy and its
  resulting output in a disposable copy where safe. Reproducing the unchanged
  blocker alone does not verify the remedy. Preserve original business inputs and
  publication state; hypothetical inputs do not establish source authority.
- After a change, repeat the original affected check and relevant regressions.
  A new passing test proves only what it exercised. Where useful show the intended
  failure before the repair and success afterwards, without modifying live data.
- For reusable generators or refreshes, read [output-refresh.md](output-refresh.md).
  Exercise changed-input and failure paths in isolation and preserve prior valid
  outputs on failure. The helper observes declared files; it does not execute,
  publish, roll back, or establish multi-file atomicity.
- Check every final status statement against its actual evidence: a local pass
  does not verify a production deployment; presence or a version label alone does
  not establish current activation. Preserve failed/partial checks and unavailable
  environments. Revisit dependent conclusions when the diagnosis changes.

Use tools already available and only authorized actions. This workflow grants no
permission to deploy, publish, alter unrelated configuration or contact others.
For a technical incident diagnosis or code-repair handover, report actual Checked / Gap / Next scope.

A Python invoked from a shell is a child process. On native Windows, when hidden
launching is required, use the available native launcher (for example PowerShell
Start-Process -WindowStyle Hidden -Wait with captured output, or Python subprocess
with CREATE_NO_WINDOW). A foreground shell invocation is not proof of no child
process or no window. Report the launch and its observable result accurately;
unavailable desktop/window evidence remains a limit.
