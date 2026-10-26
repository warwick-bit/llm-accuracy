#!/usr/bin/env python3
"""Read-only, deterministic CONFIG DOCTOR. Standard library; no network or edits."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

CATALOG = Path(__file__).with_name("checks.json")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "sessions", "transcripts", "history"}
SKIP_NAMES = {"auth.json", "credentials.json", "settings.json", "config.toml"}
VERIFY = r"re[- ]?(?:query|check)|verify (?:before|against|with)|check (?:current|live)"
SCOPE = r"does not apply|not automatically|entity being measured|requested (?:source|definition|entity)|supplied inputs|live (?:private|company)|current private"
MINIMAL_FIX = """Say plainly when a tool fails, data is absent or partial, or a source may be stale; name the affected answer.
Keep independently supported answers; mark missing values unavailable, never zero.
Do not use a draft, last-known figure or remembered sign-off as a verified fallback; disclosure does not verify it.
For mutable facts, keep a source pointer and re-check the requested period, definition and coverage before reuse.
Preserve requested source, dates, entity and comparisons; carry material limits into summaries and label supplied assumptions."""


def matches(pattern: str, text: str) -> bool:
    return re.search(pattern, text, re.I | re.S) is not None


def instruction_clauses(text: str) -> list[str]:
    """Bound lexical negation to a clause; this is not a semantic parser."""
    return re.split(r";|\.(?:\s+|$)|\b(?:but|however)\b", text, flags=re.I)


def affirmative(pattern: str, text: str) -> bool:
    """Find a cue without an explicit negation before it in the same clause."""
    for clause in instruction_clauses(text):
        for match in re.finditer(pattern, clause, re.I):
            prefix = clause[:match.start()]
            if not matches(r"\b(?:do not|don't|never|must not|should not)\b", prefix):
                return True
    return False


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def markdown_blocks(text: str) -> list[dict[str, Any]]:
    """Keep wrapped bullets/paragraphs together and cite original line spans."""
    blocks: list[dict[str, Any]] = []
    start = 0
    lines = text.splitlines()
    for i, line in enumerate(lines):
        boundary = not line.strip() or matches(r"^\s*(?:[-*] |\d+\. |#{1,6} )", line)
        if boundary and start < i:
            part = "\n".join(lines[start:i])
            if part.strip():
                blocks.append({"line": start + 1, "end_line": i, "text": part})
            start = i
        if not line.strip():
            start = i + 1
    if start < len(lines):
        blocks.append({"line": start + 1, "end_line": len(lines), "text": "\n".join(lines[start:])})
    return blocks


def python_blocks(text: str) -> list[dict[str, Any]]:
    """Only literal instruction assignments. Parsing does not execute hooks."""
    tree = ast.parse(text)
    blocks = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not any(matches(r"(?:INJECTION|REMINDER|INSTRUCTION|PROMPT).*TEXT|^INJECTION$", n) for n in names):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
        if isinstance(value, str):
            blocks.append({"line": node.lineno, "end_line": node.end_lineno,
                           "text": value, "syntax": "python-literal"})
    return sorted(blocks, key=lambda b: b["line"])


def scoped(text: str) -> bool:
    return matches(SCOPE, text)


def pressure(text: str) -> bool:
    if matches(r"(?:do not|don't|never) (?:require|instruct|tell).{0,40}(?:always|never)|(?:do not|don't) always (?:give|provide)", text):
        return False
    return matches(r"never (?:say|admit).{0,30}(?:don't know|do not know|unknown|cannot|can't)|always (?:give|provide|return) (?:a |the )?(?:number|figure|answer)", text)


def mutable_memory(text: str, path: str) -> bool:
    memory = matches(r"memory|memo|notes", path) or matches(r"final figure:|signed off.{0,35}reuse|verified from the ledger", text)
    figure = matches(r"\d[\d,.]*\s*(?:AUD|USD|NZD|%|customers|accounts|orgs)|\$\s*\d|final figure:\s*[+-]?\d", text)
    fact = matches(r"revenue|billings|balance|mrr|fx|rate|led|final figure|count|status", text)
    historical_only = matches(r"historical archive|archived fact|historical artifact", text) and matches(r"source[: ]|https?://", text) and matches(r"do not reuse|historical only", text)
    return memory and figure and fact and not matches(VERIFY, text) and not historical_only and not matches(r"^\s*(?:[-*]\s*)?(?:example|hypothetical)\s*:", text)


def scope_risks(text: str) -> list[str]:
    risks = []
    if matches(r"quantitative claims:.*each one must come from a tool result", text) and not scoped(text):
        risks.append("R01-quantitative-guard")
    if matches(r"never (?:make |give |provide )?estimat(?:e|es)|no estimates (?:ever|allowed)|every quantitative claim (?:needs|requires) a tool", text) and not matches(r"if|when|unless|supplied|scenario|live|current private", text):
        risks.append("blanket-no-estimates")
    if matches(r"before.{0,50}ANY business.metric number", text) and not scoped(text):
        risks.append("R02-registry-precedence")
    if matches(r"before computing org.state metrics.*pin the canonical definition", text) and not matches(r"live|supplied|requested (?:entity|source|window)|comparators", text):
        risks.append("R04-canonical-org")
    if matches(r"revenue comes from the general ledger", text) and not matches(r"reported accounting|order, sales|explicit.*definition", text):
        risks.append("source-date-authority")
    date_cue = r"(?:always )?use (?:the )?(?:ledger )?posting date"
    if any(affirmative(date_cue, clause) and not matches(
            r"only for (?:posting[- ]period|posting (?:period|date))|unless|requested|does not", clause)
           for clause in instruction_clauses(text)):
        risks.append("date-substitution")
    if matches(r"exclude cancelled and void records", text) and not matches(r"entity|order|invoice|does not apply", text):
        risks.append("status-cross-entity")
    if matches(r"looks wrong.*keep it out of the total", text) and not matches(r"corroborat|correct amount|evidenced error", text):
        risks.append("suspect-drop")
    if matches(r"convert to AUD.*(?:rate is missing.*stop|never assume a rate)", text) and not matches(r"user supplies|supplied|supported native|requested", text):
        risks.append("currency-global-stop")
    if matches(r"(?:ignore|omit|drop).{0,30}(?:export|comparator|saved quer)", text) and not matches(r"do not (?:ignore|omit|drop)|don't (?:ignore|omit|drop)|rather than", text):
        risks.append("comparator-suppression")
    return risks


def fallbacks(text: str) -> list[str]:
    risks = []
    if matches(r"(?:rate is missing|conversion rate is missing).*convert at 1:1", text):
        risks.append("missing-rate-parity")
    if affirmative(r"(?:treat blank values|when a value is blank, treat it) as zero", text):
        risks.append("missing-as-zero")
    if affirmative(r"(?:use|reuse|fall back to) (?:the )?(?:draft|last.known|last known) (?:figure|number|total)", text):
        risks.append("draft-fallback")
    if matches(r"signed off a figure, align with it|board.approved figures.*use it\s+for revenue", text) and not matches(r"conflicts with|check current|verify before", text):
        risks.append("signoff-authority")
    if matches(r"figures marked final are\s+signed off", text) and not matches(VERIFY, text):
        risks.append("signoff-authority")
    return risks


def caveat_suppressed(text: str) -> bool:
    explicit = matches(r"(?:omit|drop|hide|suppress|remove|no).{0,25}(?:caveats|limitations|uncertainty)|(?:never|do not|don't) mention.{0,25}(?:failures|missing data|caveats)", text)
    if matches(r"do not (?:omit|drop|hide|suppress|remove)|don't (?:omit|drop)|never (?:omit|drop)|not.*(?:omit|drop).*caveat", text):
        explicit = False
    return explicit


def memory_replacement(text: str) -> str:
    request = re.search(r'"([^"\n]+)"', text)
    pointer = f" Request to re-check: {request.group(1)}" if request else ""
    return ("- Mutable fact: retain the source locator, requested period, definition, filters and units as retrieval pointers; "
            "re-query before use. Earlier figures and sign-off are not current evidence. If the source cannot be checked, "
            "mark this answer unavailable and keep independent supported answers." + pointer)


def suggestion(code: str, subtype: str, text: str) -> str:
    if code == "D02":
        return memory_replacement(text)
    choices = {
        "R01-quantitative-guard": "For current private business facts, obtain appropriate current evidence. Calculate from supplied inputs or explicitly requested scenarios with labelled assumptions. A failed tool blocks only answers dependent on it; state the gap and keep independent supported answers.",
        "blanket-no-estimates": "Use current evidence for current private facts. Calculate from supplied inputs and give explicitly requested scenarios with labelled assumptions; do not invent missing evidence. A missing dependency blocks only its affected answer.",
        "R02-registry-precedence": "Use the pinned registry for the named company metric, matching its entity, population and requested source. Supplied or synthetic datasets keep their own definitions; show any different pinned metric separately. A failed registry lookup means unchecked, not permission to substitute a definition.",
        "R04-canonical-org": "For live company org-state claims, check the canonical definition against the requested entity, cohort and window. Preserve supplied-data calculations and requested comparators. If lookup fails, name the affected claim and retain independent supported answers.",
        "source-date-authority": "- **Source of truth:** check the agreed metric definition and authoritative report, matching its period, basis, currency and documented sign convention. For an explicitly requested order, sales or other measure, use that entity's source and requested date. Show requested exports and saved-query comparisons with their bases; an unpinned authority conflict remains unresolved.",
        "date-substitution": "Use the requested entity's date; use posting date only for a posting-period question. Disclose differing date bases rather than substituting one.",
        "status-cross-entity": "- **Status:** apply exclusions to the entity being measured and its requested status scope. An invoice's void status does not exclude a completed order. State exclusions; do not remove records without an evidenced scope reason.",
        "suspect-drop": "- **Bad data:** report suspicious values or disagreements through the agreed issue-reporting route. An unusual sign, size or late accrual alone is not an evidenced error. Correct a contribution only with corroborating evidence and disclose the basis; otherwise mark the affected total unresolved, keeping independent supported results.",
        "currency-global-stop": "- **Currency:** use requested currency, otherwise retain source currency. Convert mixed amounts with a period-matched supported rate and its documented direction. Missing rates block the conversion, leaving supported native amounts. A supplied indicative rate may support a scenario labelled as the user's assumption; never invent a rate.",
        "comparator-suppression": "Show requested comparators and their source, period and scope, even if they are not the reporting authority. Do not choose an official result without a nominated or verified basis.",
        "missing-rate-parity": "- **Currency:** a missing rate leaves the conversion unavailable; give supported native amounts. Use a supplied rate only for an explicitly labelled scenario, not as a retrieved fact.",
        "missing-as-zero": "- **Missing values:** absent or blank data is unavailable, not zero. Use zero only where the definition and evidence establish a known zero.",
        "draft-fallback": "When tools fail, say what failed and which answer lacks support. Do not endorse a draft or last-known figure as the requested verified result; keep it a separately attributed historical claim if relevant.",
        "signoff-authority": "Use the source nominated for the requested measure and verify coverage. Earlier sign-off is provenance to check, not proof of current accuracy; show supported conflicts without endorsing an unsupported fallback.",
    }
    if subtype in choices:
        return choices[subtype]
    return {
        "D01": "Answer when evidence supports the requested result. Otherwise say plainly what is unknown and why. Do not invent a number; keep independently supported parts and label requested scenarios as assumptions.",
        "D05": "Keep answers short while preserving material missing-data, stale-source and partial-coverage limits whenever the claim returns, including summaries. Do not suppress a tool failure or imply an unverified result is complete.",
        "D06": MINIMAL_FIX.splitlines()[0],
        "D07": "Include source, requested scope and material gaps where relevant. Use exact field labels only when a user, wrapper or scorer requires them. For ordinary single-source answers use one compact explanation; for complex or disputed answers include the relevant evidence details. Preserve requested amounts and comparisons before formatting.",
        "D08": "Keep one short always-on rule per invariant. Move task-specific procedures to on-demand references; record the measured loaded context before setting a profile budget. Preserve security constraints and verify any move does not hide a required rule.",
    }[code]


def make_finding(path: str, block: dict[str, Any], code: str, subtype: str,
                 checks: dict[str, Any], kind: str = "pattern") -> dict[str, Any]:
    check = checks[code]
    return {"file": path, "line": block["line"], "end_line": block["end_line"],
            "check": code, "pattern": subtype, "kind": kind,
            "why": check["why"], "evidence_level": "HYPOTHESIS" if subtype.startswith(("R01", "R02", "R04")) else check["evidence_level"],
            "evidence": check["evidence"], "source_levels": check.get("source_levels", [check["evidence_level"]] * len(check["evidence"])), "replacement_evidence_level": "HYPOTHESIS",
            # A regex cannot authorize deleting a whole paragraph. Even a single cue
            # may share its span with required controls or a valid scoped exception.
            "replacement_kind": "manual",
            "replacement_text": suggestion(code, subtype, block["text"]),
            "matched_sha256": digest(block["text"])}


def scan_text(text: str, path: str, checks: dict[str, Any], policy_gaps: bool = False,
              volume_words: int = 6000) -> dict[str, Any]:
    blocks = python_blocks(text) if Path(path).suffix == ".py" else markdown_blocks(text)
    findings = []
    for block in blocks:
        body = block["text"]
        candidates = []
        if pressure(body):
            candidates.append(("D01", "forced-answer"))
        if mutable_memory(body, path):
            candidates.append(("D02", "unverified-mutable-memory"))
        candidates.extend(("D03", item) for item in scope_risks(body))
        candidates.extend(("D04", item) for item in fallbacks(body))
        if caveat_suppressed(body):
            candidates.append(("D05", "suppressed-limits"))
        for code, subtype in candidates:
            finding = make_finding(path, block, code, subtype, checks)
            if subtype == "R02-registry-precedence":
                finding["related_locations"] = [{"file": path, "line": b["line"], "end_line": b["end_line"]} for b in blocks if matches(r"pinned entry overrides", b["text"])]
            findings.append(finding)
    if matches(r"use those labels exactly.*do not merge, rename, or omit", text) and matches(r"compact footer with.*Checked.*Gap.*Next", text):
        block = next(b for b in blocks if matches(r"use those labels exactly", b["text"]))
        finding = make_finding(path, block, "D07", "R03-footer-conflict", checks)
        other = next(b for b in blocks if matches(r"compact footer with", b["text"]))
        finding["related_locations"] = [{"file": path, "line": other["line"], "end_line": other["end_line"]}]
        finding["replacement_kind"] = "manual"  # reconcile both paragraphs, not just one
        findings.append(finding)
    # A missing instruction is not a harmful instruction. Keep advisories separate.
    if policy_gaps and text.strip() and not matches(r"(?:tool|query|source).{0,70}(?:fail|error|empty|partial|unavailable).{0,150}(?:say|state|name|disclos)|(?:say|state|name|disclos).{0,70}(?:tool|query|source).{0,70}(?:fail|error|partial|unavailable)", text):
        findings.append(make_finding(path, {"line": 1, "end_line": 1, "text": ""}, "D06", "no-explicit-failure-disclosure", checks, "advisory"))
    words = len(text.split())
    if words > volume_words:
        findings.append(make_finding(path, {"line": 1, "end_line": len(text.splitlines()), "text": ""}, "D08", "supplied-volume-review", checks, "advisory"))
    findings.sort(key=lambda f: (f["line"], f["check"], f["pattern"]))
    return {"file": path, "sha256": digest(text), "words": words, "lines": len(text.splitlines()), "findings": findings,
            "semantic_review_required": True}


def collect(paths: list[Path]) -> tuple[list[Path], list[dict[str, str]]]:
    files: set[Path] = set()
    errors = []
    for path in paths:
        if path.is_symlink():
            errors.append({"file": str(path), "error": "symlink refused"})
        elif path.is_file():
            if path.name.startswith(".env") or path.name in SKIP_NAMES or path.suffix not in {".md", ".txt", ".py"}:
                errors.append({"file": str(path), "error": "unsupported or sensitive file refused"})
            else:
                files.add(path)
        elif path.is_dir():
            # Enumerate without following directory symlinks; no imports or home discovery.
            for child in sorted(path.iterdir()):
                if child.is_symlink():
                    errors.append({"file": str(child), "error": "symlink refused"})
                elif child.is_dir() and child.name not in SKIP_DIRS:
                    found, errs = collect([child])
                    files.update(found)
                    errors.extend(errs)
                elif child.is_file() and child.suffix in {".md", ".txt"} and not child.name.startswith(".env"):
                    files.add(child)
        else:
            errors.append({"file": str(path), "error": "missing or unreadable path"})
    return sorted(files), errors


def lint_paths(paths: list[Path], policy_gaps: bool = False, volume_words: int = 6000) -> dict[str, Any]:
    checks = json.loads(CATALOG.read_text(encoding="utf-8"))
    files, errors = collect(paths)
    reports = []
    for path in files:
        try:
            reports.append(scan_text(path.read_text(encoding="utf-8"), str(path), checks, policy_gaps, volume_words))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append({"file": str(path), "error": type(exc).__name__})
    findings = [f for report in reports for f in report["findings"]]
    bundle_advisories = []
    total_words = sum(r["words"] for r in reports)
    if total_words > volume_words and reports:
        advisory = make_finding(reports[0]["file"], {"line": 1, "end_line": 1, "text": ""},
                                "D08", "supplied-volume-review", checks, "advisory")
        advisory["scope"] = "All supplied files, not an attested always-loaded bundle"
        advisory["words"] = total_words
        bundle_advisories.append(advisory)
    return {"schema": 2, "tool": "CONFIG DOCTOR v1 candidate", "read_only": True,
            "evidence_boundary": "Lexical leads only; semantic audit incomplete. Proposed text requires manual scope review. No model benefit measured.",
            "semantic_review_required": True,
            "manual_review": [
                "Read DOCTOR-PROMPT.md: review every supplied instruction, including quiet files, for meaning, negation and conflicting authority.",
                "Check mutable numeric and nonnumeric state against supplied authorized receipts; do not infer freshness from wording.",
                "Review source/date/entity/status/FX direction/cohort/NULL semantics and requested comparators.",
                "Identify old model compensations; retain/narrow/retire only with evidence and preserve required controls.",
                "Distinguish source, installation, actual launcher/hook consumption and measured model benefit; missing evidence stays unverified.",
            ],
            "volume_review_words": volume_words, "files": reports, "findings": findings,
            "errors": errors, "bundle_advisories": bundle_advisories, "supplied_words": total_words,
            "counts": {"files": len(reports), "patterns": sum(f["kind"] == "pattern" for f in findings),
                       "advisories": sum(f["kind"] == "advisory" for f in findings) + len(bundle_advisories), "read_errors": len(errors)}}


def human_report(report: dict[str, Any]) -> str:
    counts = report["counts"]
    out = [f"CONFIG DOCTOR: {counts['files']} files; {counts['patterns']} pattern warnings; {counts['advisories']} review advisories; {counts['read_errors']} read errors.",
           "Read-only. Warnings are review candidates, not proof that an answer will fail.",
           "Semantic audit incomplete: manual review required even with zero warnings. No model benefit measured."]
    out.extend("REVIEW: " + item for item in report["manual_review"])
    for f in report["findings"] + report["bundle_advisories"]:
        out.extend([f"\n{f['check']} {f['pattern']} — {f['file']}:{f['line']} ({f['kind']})",
                    f"Why: {f['why']} [{f['evidence_level']}]",
                    "Evidence: " + "; ".join(f"[{level}] {ref}" for level, ref in zip(f["source_levels"], f["evidence"])),
                    f"Proposed text [HYPOTHESIS; {f['replacement_kind']}]: {f['replacement_text']}"])
    out.extend(f"READ ERROR: {e['file']}: {e['error']}" for e in report["errors"])
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Explicit files/directories; never auto-scan your home")
    parser.add_argument("--format", choices=["human", "json"], default="human")
    parser.add_argument("--check-policy-gaps", action="store_true", help="Separate untested missing-policy advisories")
    parser.add_argument("--volume-words", type=int, default=6000, help="Review threshold, not a validated context cap")
    args = parser.parse_args()
    if args.volume_words < 1:
        parser.error("--volume-words must be positive")
    report = lint_paths(args.paths, args.check_policy_gaps, args.volume_words)
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) if args.format == "json" else human_report(report), end="\n" if args.format == "json" else "")
    return 2 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
