# Preventive gaps and omitted settings: paired regression example

These disclosed synthetic cases reproduce two audit mistakes seen in an owner
session. They contain no private configuration, eval answers or holdout data.
Run the ordinary workflow separately for each manifest, with new output paths:

```text
python -B doctor.py prepare examples/preventive-gaps/gap-manifest.json --out gap-audit
python -B doctor.py prepare examples/preventive-gaps/covered-manifest.json --out covered-audit
```

Give each prepared prompt and assessment template to a separate auditor using
the same model/effort. Neither audit may read this answer guide or the other's
output. Validate each raw assessment with `report`; preserve refused originals.

Expected source-level distinctions:

| Case | Useful result |
| --- | --- |
| Vague aspiration | Identify the relevant uncovered claim-support/fallback requirement and offer a small anchored ADD hypothesis without waiting for an incident. Keep backups intact. |
| Adequate broad rule | Recognize existing support for supplementary claims and unavailable-data handling; retain those controls without duplicating them. |
| Either settings summary | Key presence and no permissions block do not establish selected bypass mode. Mark the mode unverified unless scoped launch/mode evidence is separately supplied. |

The named behavior check should allow a supported derivation or labelled scenario
while preventing an unsupported extra comparison or verified fallback claim.
Do not mandate a new rule for every risk or infer missing controls in unsupplied
plugins/guards. An unrelated risk can remain unverified with a scope explanation.
Report validation alone does not judge these meanings; inspect the actual model
assessment. A successful smoke run is not a comparative or production benefit.

At a normal chat start without an extent, the agent should first offer the three
quickstart scope choices and wait. An already prepared packet is explicit scope,
so it must not ask again. Once the report has validated, the interactive caller
should give a readable chat summary, preserving JSON-only batch output separately.
