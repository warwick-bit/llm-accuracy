# LLM Accuracy

Use this plugin for general accuracy hygiene: claim fidelity, evidence
discipline, stale-memory rechecks, calibrated uncertainty, and self-audits of
this assistant's own prior answers.

This plugin is standalone. It does not supply a domain definition, a canonical
metric, provider access, or a deterministic source of truth. When current
evidence is unavailable, say that clearly instead of filling the gap from
memory.

For high-stakes factual claims, read `references/evidence-discipline.md` and
separate direct evidence, inference, and unchecked material. The plugin has no
provider-specific verification integration.

The bundled evidence-receipt validator checks structure only. It is stateless,
does not read transcripts or provider data, and must never be described as an
accuracy or domain-correctness certificate.
