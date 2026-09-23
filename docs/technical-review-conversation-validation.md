# Conversational challenge completed: no added benefit demonstrated

**Conclusion: keep the candidate draft, not a general accuracy fix.** The final
declared pass completed three multi-turn conversations and their reviews. Two
final answers had no material issue identified; the third remains disputed.
The product reviewer returned no findings in all three. The final-source
installation smoke passed, but no added detection benefit was demonstrated.
The experiment is closed without another prompt/model/rubric retry. See the final
pass below; earlier failures remain part of the record.

The ten-case pilot used authored drafts and tidy
evidence packets. Native installation smokes used real Claude sessions but did
not establish accuracy on vague, evolving conversations.

Four additional synthetic session patterns were prepared: vague closure pressure,
a correction from production to sandbox scope, conflicting rollout reports, and
actual local Read/Bash inspection of a fictional retry repository. Three have
multiple user turns. These are designed examples, not demonstrated coverage of
real user work. [Prepared fixtures](../tests/fixtures/technical-review-conversations.json).

The initial plan required an assessor to distinguish appropriate, missed and spurious
review findings on authored calibration controls before running subject sessions.
It did not pass. **Those three registrations ran no conversational subjects.**

- Initial Sonnet calibration stopped at an unscorable clean control. A separate
  diagnostic returned an incomplete judgment anchored in the draft while the
  parser required the question. That did not rescore the failed calibration.
- A new registration declared the anchor explicitly and clarified required
  versus optional gold content. Its supported control also explicitly attributed
  the local test report and stated that no tracker status was supplied. Sonnet
  matched all six controls initially and the first reversed control, then judged
  the same supplied omission finding as missed. The frozen gate failed.
- One final registration changed only the assessor to Opus 5.5 medium. It matched
  the first five controls, then returned an unscorable result on the overhedging
  control. The attempt stopped; no further model or rubric retry followed within
  that calibration sequence.

[Typed calibration receipts](validation/technical-review-conversation-calibration-2026-09-23.json)
retain the frozen dependency hashes, host metadata, validated labels and quote
positions. No raw answers or tool output are saved. These failures establish an
assessment gap, not a measured failure or benefit of the proposed reviewer.
The fixture localization pilot, deterministic tests and installation checks
remain separate evidence layers.

A future conversational evaluation needs a dependable adjudication method,
including explicit decisions about required versus optional content and a way
to verify that each omission was actually identified. Independent human
adjudication of bounded, authorized real examples would strengthen that evidence.
Even a successful small synthetic challenge would not establish general accuracy
or coverage of long context, compaction, tools and private runtime policies.

## Subsequent direct inspection

A separate method ran the four prepared scenarios in real Claude Code processes
at source commit `6bfc6a3ce1c38824f817878b966be18176c799bf`. Opus 5.5 medium authored
the answers; the public runner’s Fable reviewer received only complete questions,
drafts and attributed evidence, never fixture gold. A fresh-context Codex reviewer
first froze its claim inventory without seeing product findings, then reconciled
the findings with the parent. Four direct inspection controls distinguished a
supported answer, unsupported recovery, omitted production status and excessive
hedging. This is model-assisted inspection, not human-adjudicated ground truth.

```text
Scenario             Subject outcome          Product review
Vague closure        Opening-turn host error  Not invoked
Scope correction     240-second timeout       Not invoked
Conflicting rollout  240-second timeout       Not invoked
Local repository     Completed                No findings
```

The first invalid run stopped the original acceptance path. A recorded amendment
ran the remaining scenarios once for coverage only, retaining the failure and
forbidding replication or a cohort-pass claim. **No valid multi-turn reviewer
evaluation resulted.** The completed repository case was single-turn: actual
Read/Bash results confirmed file inspection and test execution, exact hook context
was observed, and the fixture remained unchanged. Claude distinguished a passing
health test from untested retry behavior and unknown production recovery. The
blind reviewer and parent identified no material defect; the product's empty
finding set agreed. This supplies no evidence of added detection benefit.

The invalid closure run's later answer treated an older build as proof of
nondeployment. Direct inspection exposed an interpretation dispute: nondeployment
is not entailed without change/build timing, although the conversational contrast
can suggest it. This remains an unscored diagnostic, not an agreed defect count.

The run also exposed a diagnostic weakness: the host classified errors using the
entire transcript, so an unrelated ID containing `429` or a successful answer
mentioning authentication could determine the reported cause. Synthetic regression
tests reproduced this. The subsequent fix restricts classification to failed-result
diagnostic fields and stderr, avoids matching arbitrary larger numbers, and does
not treat a generic expired deadline as authentication. These are still heuristic
indicators. The original run's rate-limit label does not establish its actual
cause, and the fix does not resolve the Claude tool-call error or silent timeouts.

The unused gold text for the local repository was also corrected from “retries
twice” to at most two calls, or one retry. No subject or product reviewer saw this
gold, and no failed attempt was rescored or replaced.

[Typed direct-inspection receipts](validation/technical-review-conversation-direct-2026-09-23.json)
preserve source hashes, runtime metadata and all four outcomes. The driver kept
answers in memory and displayed synthetic material for direct inspection; it did
not write raw answer files. Native session persistence was disabled; parent
conversation and provider retention still apply. Runtime isolation deliberately
excluded the user's private harness. The headless failures do not establish the
same behavior in an ordinary interactive session or on the user's other machine.

At that checkpoint, reliable multi-turn completion and meaningful error
detection remained unestablished. The fixed host classification passed its separate code tests and a
[fresh installation check](validation/technical-review-install-current-2026-09-23.json);
that does not turn this evaluation into an accuracy pass.

## Altered-context follow-up: usage limit

An unscored diagnostic added only a generic instruction to respond in text and
ask clarification questions in plain text when tools are unavailable. The same
scope-correction conversation completed all three turns in 26.9 seconds with
the exact hook sequence. This is one completion observation, not proof that the
instruction fixes the earlier intermittent failure. It also changes the author's
system context, so it is not an ordinary-session or unchanged-context result.

A new frozen arm declared one pass of the three multi-turn cases under that
context, with fresh blind Sonnet assessment before exposing Fable findings.
Its first subject returned an explicit session usage-limit notice. No product
review or assessor ran; the other two cases were left unattempted to avoid
repeating calls against the account limit. No model substitution, repetition or
replacement of the earlier cohort occurred. [Typed record](validation/technical-review-conversation-text-2026-09-23.json).

The host now also recognizes that explicit session-limit phrase as a limit
indicator. The earlier authenticated installation smoke predates this final
classification-only addition. Deterministic regression tests cover the addition;
another authenticated final-build smoke and the unfinished multi-turn assessment
were deferred until account availability returned. Login refresh is not indicated by a usage
limit. At that checkpoint there was no completed multi-turn reviewer result.

While waiting, an independent code review reproduced an inherited stream-framing
bug: Python's `splitlines()` treated literal Unicode separators inside valid JSON
strings as event boundaries. This could discard an answer or hook event. The host
now splits only on LF; regression tests cover three Unicode separators, LF/CRLF
streams and actual two-turn subprocess communication. The existing installation
receipt predates this fix too. No reviewer instructions or conversational cases
changed, and no earlier failed result was rescored.

## Final declared pass and conclusion

After the user reported that account access had reset, the three unchanged
conversations ran once at source `53bfdaab0bfcf06d4ed4323af9874d061fbb6d81`.
The user explicitly authorized execution alongside another Claude review batch;
concurrent load limits latency and failure attribution. The author still used
the declared plain-text clarification envelope. No product prompt, case, model,
assessment criterion or earlier outcome was changed.

Opus 5.5 medium completed all three turns in each conversation, with session
continuity and the exact hook sequence verified. Each fresh Sonnet 5 medium
assessor inspected the same four direct controls and then the complete
conversation before product findings were exposed. Fable 5.1 returned an empty
finding set for each final draft.

```text
Scenario             Parent inspection             Product review
Vague closure        Disputed inference             No findings
Scope correction     No material issue identified   No findings
Conflicting rollout  No material issue identified   No findings
```

The scope-correction answer preserved the sandbox/live distinction and labelled
possible causes as unconfirmed. The rollout handover preserved the reported
Closed ticket while leaving endpoint recovery and service identity unverified.
These are clean-answer observations, with no demonstrated detection headroom.

The closure answer inferred nondeployment from an older live build and described
the customer issue as remaining open. Build age alone does not entail absence
of the tweak without timing information; “open” also has colloquial versus
recorded-status ambiguity. The blind assessor accepted these clauses, even
describing nondeployment as directly supported. The parent disagreed with that
entailment judgment. Under the declared disagreement rule this case remains
disputed/unscored, not a clean pass or a confirmed detection-rate denominator.
Passing the four controls did not make the assessor a source of ground truth.

[Typed final receipts](validation/technical-review-conversation-final-2026-09-23.json)
preserve source hashes, runtime metadata, all outcomes and the disagreement
without raw answers. Only final answers were assessed; no rewrite benefit,
representative accuracy rate or human-adjudicated ground truth was measured.
Successful completion under changed context does not prove a causal fix for
earlier headless failures or coverage of ordinary interactive/private harnesses.

The [final-source installation smoke](validation/technical-review-install-final-2026-09-23.json)
passed marketplace installation, source matching, native invocation, default and
custom triggers, bypass and ZIP loading. Its seeded status error was flagged.
An additional unidentified host component in native/custom/bypass sessions limits
isolation claims. This is functional evidence, separate from semantic reliability.

**Decision:** the declared experiment is finished. Keep the reviewer optional and
unreleased in the draft PR; this record does not justify promoting it as the
general solution to overconfident technical answers. Existing automatic rules
remain unchanged. Further promotion would need a separately agreed evidence
contract, not repeated attempts to make this cohort pass.
