#!/usr/bin/env python3
"""Resolve declared local text references and check quotations, never semantic support."""
import argparse
import hashlib
import json
from pathlib import Path

from check_numerical_claims import unique_object


def text_value(value):
    return isinstance(value, str) and bool(value.strip())


def validate_manifest(manifest):
    if not isinstance(manifest, dict) or set(manifest) != {"sources", "citations"}:
        raise ValueError("Manifest needs sources and citations")
    sources, citations = manifest["sources"], manifest["citations"]
    if not isinstance(sources, dict) or not all(text_value(key) for key in sources):
        raise ValueError("sources must map nonempty source IDs to path/url definitions")
    for source in sources.values():
        if (not isinstance(source, dict) or not source or set(source) - {"path", "url"}
                or not all(text_value(value) for value in source.values())):
            raise ValueError("Each source needs a nonempty path and/or URL")
    if not isinstance(citations, list):
        raise ValueError("citations must be a list")
    seen = set()
    for citation in citations:
        if (not isinstance(citation, dict) or not {"id", "source_id", "claim"} <= set(citation)
                or set(citation) - {"id", "source_id", "claim", "quote"}
                or not all(text_value(value) for value in citation.values())):
            raise ValueError("Each citation needs id, source_id, claim and an optional nonempty quote")
        if citation["id"] in seen:
            raise ValueError("Citation IDs must be unique")
        seen.add(citation["id"])


def read_source(definition, directory):
    if definition is None:
        return {"reference_check": "unresolved", "reason": "Source ID is not declared"}, None
    evidence = {"live_url_status": "not_checked"} if "url" in definition else {}
    path = definition.get("path")
    if path is None:
        return dict(evidence, reference_check="needs_host_retrieval",
                    reason="Use an available host tool to retrieve the URL; supply a text snapshot"), None
    if "://" in path:
        return dict(evidence, reference_check="unresolved", reason="path must name a local text file"), None
    try:
        raw = (directory / path).read_bytes()
        evidence["source_sha256"] = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, ValueError):
        return dict(evidence, reference_check="unavailable", reason="Local UTF-8 source could not be read"), None
    return dict(evidence, reference_check="resolved_local_snapshot"), text


def check_citations(manifest, directory):
    validate_manifest(manifest)
    sources, results = {}, []
    for citation in manifest["citations"]:
        source_id = citation["source_id"]
        if source_id not in sources:
            sources[source_id] = read_source(manifest["sources"].get(source_id), directory)
        reference, text = sources[source_id]
        result = dict(citation, **reference, claim_support="not_verified")
        quote = citation.get("quote")
        if quote is None:
            result["quote_check"] = "not_requested"
        elif text is None:
            result["quote_check"] = "not_checked"
        else:
            quote = quote.replace("\r\n", "\n").replace("\r", "\n")
            position = text.find(quote)
            result["quote_check"] = "found" if position >= 0 else "not_found"
            if position >= 0:
                result["first_match"] = {"start_line": text[:position].count("\n") + 1,
                                         "end_line": text[:position + len(quote) - 1].count("\n") + 1}
        results.append(result)
    return {"execution": "completed", "citations": results,
            "coverage": "Every declared citation retained; unlisted report claims and references were not inspected",
            "matching": "Exact text after normalizing line endings; no ellipsis, paraphrase or whitespace inference",
            "authority": "Reference resolution and quotation matching only; source truth, authority, live URL reachability and claim entailment are not verified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="JSON with sources and citations; source paths resolve beside this file")
    args = parser.parse_args()
    try:
        raw = args.manifest.read_bytes()
        result = check_citations(json.loads(raw, object_pairs_hook=unique_object), args.manifest.resolve().parent)
        result["sha256"] = {"manifest": hashlib.sha256(raw).hexdigest(),
                            "checker": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            "json_decoder": hashlib.sha256(Path(__file__).with_name("check_numerical_claims.py").read_bytes()).hexdigest()}
    except (OSError, ValueError, RecursionError):
        print(json.dumps({"execution": "error", "error": "Citation manifest is unreadable or invalid"}))
        return 2
    print(json.dumps(result, indent=2))
    return 0  # Inspect each reference/quote result, not merely successful execution.


if __name__ == "__main__":
    raise SystemExit(main())
