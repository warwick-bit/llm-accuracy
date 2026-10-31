---
name: saved-output-audit
description: Use when creating, revising or checking a saved factual report, spreadsheet handover or versioned output against supplied sources and earlier reports. Check the actual final file, historical claims and correction explanations; preserve correct history. Also use when a claimed file was not delivered.
argument-hint: "[report and its source files or supplied snapshots]"
---

# Saved-output audit

Deliver the user's requested file and check its contents against the evidence.
Keep the check proportionate. This skill is not an independent reviewer and its
helper does not certify whole-report accuracy.

1. Read `references/saved-output-repair.md` relative to this skill's own
   directory (the directory containing this SKILL.md). Its scripts and reference
   are bundled here so a host can mount this skill independently of the plugin
   root. Use the current host's real tools and permissions.
2. Separate current facts, actual earlier versions and explanations of changes.
   A new source value does not make an older own-source answer wrong. Preserve
   IDs, dates, source scope, membership, ranking and original historical errors.
   Check each material prose claim, including any account of when instructions
   arrived. A later error is not evidence that an earlier claim was false.
   Before delivery, reconcile every claim in the explanation against the final
   saved output and the sources: each statement that a value changed or did not
   change, or that a figure, method or earlier report is valid, invalid, correct
   or wrong. A correct component figure stays correct even when an aggregate
   built from it is wrong: name the actual flaw (for example the method of
   combining) rather than disputing correct inputs. Remove or correct any claim
   the data does not support.
3. Inspect the actual saved file after writing it. Recompute required fields
   from the supplied sources with deterministic tools when available. Correct
   numbers do not establish a correct explanation or prove a tool was used.
4. On a host with Python and access to these packaged scripts, run
   this skill's `scripts/check_saved_output.py` on the actual report and any saved delivery
   text. Resolve a working Python executable first; do not assume `python3`.
   For example, using resolved paths as separate arguments:

   ```text
   PYTHON SKILL_DIRECTORY/scripts/check_saved_output.py REPORT --version v3 --source v1=EARLIER_REPORT_1 --source v2=EARLIER_REPORT_2 --delivery DELIVERY_TEXT
   ```

   Omit optional arguments for unavailable files; never reconstruct earlier
   bytes and claim they are original. The helper is read-only and stateless.
   Read its JSON status and limits, not only its exit code. If citing a computed
   hash, use the explicit label `SHA-256 v3: <full digest>` (or its actual version). It checks plainly
   labelled single literal formula equalities and version-labelled SHA-256
   claims. Percentage-valued equations, units, source truth and other prose
   require separate checks. Fenced and blockquoted historical equations are
   excluded; verify attribution before changing any quoted claim.
5. Repair only supported discrepancies. Keep the original versions unchanged.
   After each edit, reread and recheck the actual new bytes, including narrative
   corrections and delivery text. Use at most two correction attempts for this
   check; if errors or missing evidence remain, state them. Do not call a pass
   of these bounded checks a complete audit. A factual claim that *only* the
   version label changed is inaccurate when history also gained an entry;
   describe unchanged current values separately from changed version/history.
6. Expose the final file through the host's supported download mechanism.
   A path or filename alone is not delivery. If a previously claimed file is
   missing, retrieve that existing file first. If retrieval fails, say it is
   unavailable; do not quietly regenerate it or assert original byte identity.

On Chat or another host without script/file execution, apply the evidence checks
to the supplied snapshots and name the unavailable byte-level checks. Do not
simulate helper output. A separately launched external reviewer/controller may
provide feedback; this plugin does not start one or claim that one ran.

Return the file and a short account of material corrections and remaining gaps.
Keep a generated helper receipt separate from the report. Do not alter source
files or add process claims merely to make the check appear successful.
