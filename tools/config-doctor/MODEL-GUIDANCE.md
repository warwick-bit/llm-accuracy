# Primary guidance checked 18 October 2026

These are review questions, not measured findings about the owner's harness.
No inference here authorizes changing routes, effort, safety controls or a live home.

[Anthropic: Prompting Claude Opus 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5).
The guide recommends testing effort for the workload; it discusses removing
forced reasoning narration and revisiting mitigations for earlier thinking-disabled
integrations. It also explains that unattended runs may stop after progress, so
continuation controls can still matter. Review questions: does a no-thinking rule
conflict with the selected integration, does a narration rule serve a useful user
need, and is apparent silence a rendering/delivery issue? Preserve essential checks
and irreversible-action confirmation. No local model benefit has been measured.

[Anthropic: Prompting Claude Sonnet 5.5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5-5).
The guide says effort affects initiative, premature stopping and verification.
Its completion advice combines carrying authorized work through with stopping once
requested work and checks are complete. Its JSON-specific advice differs from
generic chat advice. Review questions: is a completion/verification instruction
still needed, is a review loop creating extra scope, and does the task-specific
reasoning guidance actually apply? Do not retire all reminders or copy Opus advice
to Sonnet indiscriminately. No local model behavior has been tested.

[Claude Code: How Claude remembers your project](https://code.claude.com/docs/en/memory).
Instruction text is context, not enforcement. File imports, path-scoped rules and
consumer configuration affect what loads; existence alone is insufficient evidence.
Review questions: are duplicates actually consumed together, and is an old loading
workaround redundant for the installed version? Obtain a safe loading receipt in a
separate authorized validation before claiming activation. Do not run commands or
inspect the active collector to obtain one during this task.

## Additional primary guidance checked 20 October 2026

[OpenAI: skills and prompts for GPT-6 Astra](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra).
Review supplied skill descriptions for overly broad triggers and competing
workflows; keep task-specific material behind relevant references. Advice for
Astra is not evidence that Sol/Luna no longer need a completion or verification
control. No model/effort change or automatic skill removal follows from this page.

[OpenAI: AGENTS.md loading](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
Selected CODEX_HOME, overrides, root-to-working-directory order, configured
fallback names and the configured combined byte limit affect instruction receipt.
The documented default limit is 32 KiB, not an optimal prompt-size recommendation.
Use explicit supplied configuration/loading receipts; never discover a live home
or infer loading just because the file exists. This is loading guidance, not a
Codex model-specific fidelity guarantee.

[Anthropic: native instruction audit](https://code.claude.com/docs/en/memory#audit-your-instruction-files).
The documented `/doctor prompt-audit` requires Claude Code v2.1.283+ and the
bundled Claude API skill. It accepts a specific file/directory; its default scope
is broader than this tool's explicit manifest. Compare matched selected snapshots,
not a broad native scan against a narrow Doctor packet. See COMPARISON.md.
