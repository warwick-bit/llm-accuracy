# LLM Accuracy 0.6.4

This patch gives the five advisory hooks ten seconds to finish, up from three.
Large tool results could previously exhaust the declared timeout and lose the
advice. The commands and fail-open behavior are unchanged. A stalled hook can
now delay a turn for up to ten seconds.

Hook input is decoded as UTF-8 on Windows and other hosts regardless of the
pipe's locale encoding. Receipt and catalogue validators return structured
failures for malformed enum values and overly deep JSON. The optional host
probe falls back to killing its owned child if macOS denies a process-group
signal. Descendant cleanup remains best-effort in that denied-signal case.

## Update

```sh
claude plugin marketplace update llm-accuracy
claude plugin update llm-accuracy@llm-accuracy
```

Start a new Claude Code session or run `/reload-plugins`, then confirm package
`0.6.4` in `/llm-accuracy:accuracy-doctor`. ZIP users can use the
`llm-accuracy-0.6.4.zip` release asset. See the [install guide](INSTALL.md).

## Validation and limits

The combined source passed 868 local tests, Ruff, hook compilation, JSON and
distribution checks, a clean isolated marketplace install, and Linux,
Windows Git Bash and macOS CI. The timeout change reduces one cause of lost
advice; it does not prove that every live timeout notice is fixed or that
answers are more accurate. Observe a fresh installed session if notices recur.
