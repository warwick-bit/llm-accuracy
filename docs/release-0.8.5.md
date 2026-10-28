# LLM Accuracy 0.8.5

This release strengthens the existing checks for the files, explanations and
recommendations people actually receive.

## Changes

- Check the meaning of generated explanations and saved examples against the
  evidence. Matching saved output to live output can reproduce the same mistake.
- Correct misleading outputs at their source and regenerate them, or visibly
  supersede them with a usable corrected alternative.
- Preserve the checked identities, order and cutoff when shortening a ranked
  list or recommending replacements.
- Test the exact proposed recovery action safely, including the rules that block
  it. A successful hypothetical check does not decide which source is authoritative.
- Keep assertion inventories optional, after the substantive output checks.

These are changes to four existing guidance files. The plugin continues to use
its existing advisory skills and helpers.

## Qualification and limits

The [live bundle receipt](validation/claude-bundle-smoke-0.8.5.json) and
[Accuracy installation/archive receipt](validation/claude-code-smoke-0.8.5.json)
record the final package's native Windows qualification. Publication requires
the release gates, including installed-hook checks on Linux, macOS and Windows
with and without Git Bash. Other live and UI coverage remains as recorded in
the compatibility matrix; these terminal checks do not certify Desktop or Cowork.

Eight selected local development replays across two revisions informed this
change. The final revision repaired the primary misleading explanation in the
Sol and Sonnet replays. Sonnet still left an older instruction in a linked
secondary example; an earlier shortened update also mislabelled a population.
These findings remain limits, not failures erased from the results. The trials
do not establish a prevention rate or reliable behavior in every long session.

The plugin improves evidence discipline; following its guidance remains
model-dependent and does not guarantee correctness. Codex remains skills-only.

## Update

Refresh the `warwick-bit/llm-accuracy` repository marketplace in Claude or Codex,
update **LLM Accuracy**, confirm **0.8.5**, and start a new conversation.
