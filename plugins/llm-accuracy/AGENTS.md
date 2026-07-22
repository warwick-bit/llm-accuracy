# LLM Accuracy

Use this plugin for general accuracy hygiene: evidence discipline, stale-memory
rechecks, calibrated uncertainty, and self-audits of this assistant's own prior
answers.

This plugin is standalone. It does not supply a domain definition, a canonical
metric, provider access, or a deterministic source of truth. When current
evidence is unavailable, say that clearly instead of filling the gap from
memory.

For high-stakes factual claims, read `references/evidence-discipline.md` and
separate direct evidence, inference, and unchecked material. The plugin has no
provider-specific verification integration in this preview.
