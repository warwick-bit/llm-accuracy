# Data-access tips: test record

Raw-free figures behind the README's
[data-access tips](../README.md#tips-from-our-data-access-tests). Recorded
4 Oct 2026. These tests measured how Claude Code handles fetched data under
different access routes. They do not test the published LLM Accuracy plugins
(the file-workflow pilot used an unpublished one) or measure an overall
accuracy rate.

## Access-route screen

- **Host:** Claude Code `--print`, subscription session, high effort.
- **Models:** `claude-sonnet-5-5`, `claude-opus-5-5`.
- **Fixture:** one synthetic invoices and payments database, 600 invoices,
  fixed seed; 8 exact questions per run; 3 runs per model and route.
- **Routes:**
  - SQL tool over MCP: SQL in, computed result out.
  - Records tool over MCP: raw 100-row record pages into the conversation.
  - SQL CLI: SQL through a command the model runs in Bash.
  - Records CLI: raw record pages through a command the model runs in Bash.
- **Exactness:** 24/24 in every model and route.

```text
Model   Route                Cost (3 runs)  Median secs  Median input tokens
Sonnet  SQL tool over MCP    $0.16           19           34k
Sonnet  Records over MCP     $2.12          103          796k
Sonnet  SQL CLI              $0.16           28           39k
Sonnet  Records CLI          $0.15           22           26k
Opus    SQL tool over MCP    $0.37           27           43k
Opus    Records over MCP     $3.80          124          694k
Opus    SQL CLI              $0.31           32           32k
Opus    Records CLI          $0.42           35           38k
```

- **Mechanism:** with raw records in the conversation, both models wrote the
  page rows into files through Bash heredocs (17 of 17 and 17 of 18 Bash calls)
  and computed over them. The median such command held about 800 numeric
  literals, against 4 to 7 on the records CLI route.
- **Size screen:** at 4,000 invoices (Sonnet, one run per route) every route
  was exact (8/8). Records over MCP cost $9.38 and took 873 seconds; the other
  routes cost $0.05 to $0.06 and took 20 to 47 seconds.
- **Limits:**
  - one synthetic fixture and two sizes; every route hit the exactness
    ceiling, so the test cannot rank routes on accuracy;
  - three runs per cell at 600 invoices and one at 4,000, so no variance
    estimate at 4,000;
  - MCP results reached the model as escaped JSON, 1.09 to 1.16 times as
    many characters as plain text, a small part of the token gap;
  - both sizes ran on work-in-progress versions of the harness (the 4,000-invoice
    screen on an earlier one), and neither was re-run on the final version;
  - costs are the CLI-reported figures, not billed dollars.

## File-workflow pilot

- **Source:** [native validation note](https://github.com/warwick-bit/llm-accuracy/blob/11ede6167e769dccfa71902903ca1ce6fa45c0fe/docs/data-execution-native-validation.md)
  on the unmerged `feat/data-execution-plugin` branch.
- **Host:** Claude Code 2.1.280, `claude-sonnet-5`, low effort.
- **Fixture:** one 400-row synthetic mixed-currency workflow (aggregate, then
  selected detail in a fresh session); one run per setup.
- **Result:** raw fetch and follow-up 236,331 reported tokens; existing file
  helper and follow-up 90,383; the pilot's capture plugin and follow-up
  183,275. All requested fields exact.
- **Limits:**
  - one observation per setup, no variance estimate;
  - totals sum input, cache creation, cache reads and output, so they are not
    unique context size or billed cost;
  - the raw arm was told to fetch raw, and its large output spilled to a file,
    so it does not estimate unaided Claude.

## Automatic file-pointer hook

- **Source:** [automatic validation note](https://github.com/warwick-bit/llm-accuracy/blob/11ede6167e769dccfa71902903ca1ce6fa45c0fe/docs/data-execution-automatic-validation.md)
  on the same branch.
- **Host:** Claude Code 2.1.280, `claude-sonnet-5`, low effort; one run per
  case and version; synthetic sources only.

```text
Case                          Token change vs native
Pointer v1, medium, Bash      +106.7%
Pointer v1, medium, MCP       +146.3%
Pointer v2, medium, Bash       +46.0%
Pointer v2, medium, MCP        +13.6%
```

- **Mechanism:**
  - **v1:** with a file reference in place of the output, Claude often read the
    full file back, adding calls and context.
  - **v2:** added guidance to calculate over the file. Its medium cases still
    used more tokens; the note gives no cause.
  - **Fidelity:** for a 152,453-byte Bash output, v1 received a 30,000-character
    preview and saved it as if it were the whole source.
- **Exactness:** all completed comparisons were exact.
