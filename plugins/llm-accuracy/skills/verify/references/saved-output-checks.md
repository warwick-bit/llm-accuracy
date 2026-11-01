# Saved-output checks

Read [saved-output-repair.md](saved-output-repair.md) for source/history boundaries.
Resolve `<skill-directory>` to the directory containing SKILL.md for helper commands.

- Separate current source facts, what each actual earlier file contained, and what
  the evidence establishes about a correction. A later source update does not make
  an earlier own-source answer wrong. Keep source snapshots and prior reports immutable.
  Do not reconstruct missing earlier bytes or imply they are the original files.
- Check the requested fields and prose in the actual final file after writing it:
  IDs, dates, statuses, units, membership, rank, totals and recommendations where
  applicable. Recompute required fields from the supplied sources. An accurate
  companion note does not repair a contradictory deliverable.
- Treat every correction explanation as a factual claim. Preserve correct component
  values when the aggregation is wrong. Earlier contents show what was written,
  not how it was produced. Do not claim a particular calculation, missing check,
  instruction timing or causal history without process evidence.
- With file access and Python, run `<skill-directory>/scripts/check_saved_output.py`
  on the actual report and saved delivery text, supplying available original versions
  with `--source VERSION=PATH`. Inspect its status and limits, not just exit zero.
  It checks labelled literal formula equalities and version-labelled SHA-256 claims;
  percentage-valued equations, units, source truth and other prose need separate
  checks. Historical fenced/quoted equations are excluded; check attribution yourself.
- Repair supported discrepancies, then reread and recheck the final bytes and
  delivery wording. Use at most two attempts for this bounded repair check; retain
  unresolved errors or missing evidence instead of claiming a pass. Do not change
  source files merely to make a report or helper pass.
- If citing a digest, compute it and label it `SHA-256 v3: <full digest>` using the
  actual version. A matching hash does not establish that an author ran a check.
- Deliver the requested file through the host's supported mechanism. If a previously
  claimed file is missing, first try to retrieve it; if unavailable, say so. Do not
  silently regenerate it or claim original byte identity. A filename alone is not delivery.

On a host without file/script execution, apply the available source checks to the
supplied snapshots and name the unavailable checks. Never simulate helper output
or an independent review. Keep the delivered report and any helper receipt distinct.
