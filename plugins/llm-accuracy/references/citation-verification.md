# Check references and quotations

Use this workflow for supplied report references, quotations or cited claims.
Separate reference resolution, quote presence and support for the surrounding
claim. A source can contain the exact words and still contradict the conclusion.

1. Inventory the material cited claims and keep their original wording. A
   selected manifest is not proof that every citation or side claim was included.
2. Resolve each reference with available host tools. For a URL, use the existing
   browser/connector retrieval tool and inspect its actual response, destination
   and relevant section. Do not equate a search snippet, login page or successful
   HTTP request with access to the cited source. Failed/unavailable retrieval
   remains explicit. Do not activate an integration just for this workflow.
3. On an execution-capable host, preserve the actual returned text in a temporary
   UTF-8 snapshot and use the helper below. For PDFs or other nontext files, use
   an available reader to extract the relevant text and retain the original source
   and extraction limits. Never reconstruct a missing quotation from memory.
4. Inspect quote checks and then assess meaning: speaker, population, date,
   conditions, exclusions, negation and causal scope. Distinguish a source's
   assertion from an independently established fact. Record this semantic
   assessment separately; the helper always reports `claim_support: not_verified`.
5. Correct supported errors, retain useful supported content, and disclose
   unresolved citations. Rerun after source or quote changes. Keep input sources
   unchanged; save an audit only when the task requires that deliverable.

## Local helper

Resolve the script from this installed package, use working Python 3.9+, and
quote absolute paths. If execution is unavailable, say the helper did not run.

```text
python "<plugin-root>/scripts/check_citations.py" citations.json
```

Example manifest with fictional references:

```json
{
  "sources": {
    "study": {"path": "study.txt", "url": "https://example.invalid/study"},
    "unavailable": {"url": "https://example.invalid/missing"}
  },
  "citations": [
    {
      "id": "price-mention",
      "source_id": "study",
      "claim": "Price caused the cancellations.",
      "quote": "Some respondents mentioned price."
    },
    {"id": "other", "source_id": "unavailable", "claim": "Another source-backed claim."}
  ]
}
```

Local paths resolve relative to the manifest, irrespective of the working
directory. Source and citation IDs must be explicit; citation IDs are unique.
Each source has a local `path`, a provenance `url`, or both. URL-only references
return `needs_host_retrieval`; this script makes no network calls. A URL attached
to a local snapshot still has `live_url_status: not_checked`. Report separately
what the host retrieval actually established; a URL label is not authentication.

Quotation checks are exact after normalizing line endings. They do not expand
ellipses, infer paraphrases or ignore arbitrary whitespace. The first matching
line range and raw source hash identify the inspected snapshot. A missing quote
is `not_found`, not a verdict that the surrounding claim is false. A reference
without a quote can resolve, but has `quote_check: not_requested`.

Every declared citation is retained. Missing files/unknown source IDs leave
dependent quote checks `not_checked`; independent available references are still
checked. Unsupported encoding remains unavailable. Duplicate JSON fields and
ambiguous manifests fail with a structured execution error. Exit zero means the
checks completed, not that all references or claims passed. Output is JSON on
stdout; the checker does not modify source files or reports.
