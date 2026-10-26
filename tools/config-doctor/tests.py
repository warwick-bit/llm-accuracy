"""Behavioral contracts for bounded scanning and review-only delivery."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import lint

HERE = Path(__file__).resolve().parent
CHECKS = json.loads((HERE / "checks.json").read_text(encoding="utf-8"))

class DoctorTests(unittest.TestCase):
    def patterns(self, text, path="AGENTS.md"):
        return {f["pattern"] for f in lint.scan_text(text, path, CHECKS)["findings"]
                if f["kind"] == "pattern"}

    def test_scoped_negation(self):
        self.assertNotIn("missing-as-zero", self.patterns(
            "Do not treat blank values as zero; missing balances remain unavailable."))
        self.assertIn("missing-as-zero", self.patterns("Treat blank values as zero."))
        self.assertIn("missing-as-zero", self.patterns("When a value is blank, treat it as zero."))
        self.assertNotIn("missing-as-zero", self.patterns("Do not\n  treat blank values as zero."))
        self.assertNotIn("date-substitution", self.patterns(
            "Use posting date only for posting-period figures; re-query before reuse."))
        self.assertIn("date-substitution", self.patterns("Always use the posting date."))

    def test_mixed_clauses(self):
        # Valid controls elsewhere in a paragraph must not hide harmful directives.
        self.assertIn("draft-fallback", self.patterns(
            "Never disclose credentials; if the warehouse fails, use the draft figure."))
        self.assertIn("missing-as-zero", self.patterns(
            "Never treat blank values as zero; however treat blank values as zero for the final total."))
        self.assertIn("date-substitution", self.patterns(
            "Use posting date only for posting-period figures. Always use posting date for sales."))
        self.assertIn("draft-fallback", self.patterns(
            "Never use the draft figure. But reuse the last-known total."))
        self.assertNotIn("draft-fallback", self.patterns("Never use the draft figure as verified."))

    def test_manual_scope_preserves_controls(self):
        text = "# Rules\n\n- Always give a number. Never disclose credentials.\n  Keep source context.\n- Preserve backups.\n"
        report = lint.scan_text(text, "AGENTS.md", CHECKS)
        finding = report["findings"][0]
        self.assertEqual((3, 4), (finding["line"], finding["end_line"]))
        self.assertEqual("manual", finding["replacement_kind"])
        self.assertEqual(lint.digest("\n".join(text.splitlines()[2:4])), finding["matched_sha256"])
        self.assertTrue(report["semantic_review_required"])
        # A Python source assignment also stays manual and is never executed.
        result = lint.scan_text('raise RuntimeError("do not execute")\nINJECTION_TEXT = "Always give a number."', "hook.py", CHECKS)
        self.assertEqual("manual", result["findings"][0]["replacement_kind"])

    def test_cli_review_boundary(self):
        with tempfile.TemporaryDirectory(prefix="doctor-cli-") as folder:
            root = Path(folder)
            safe = root / "CLAUDE.md"
            safe.write_text("Keep replies clear.\n", encoding="utf-8")
            before = safe.read_bytes()
            for fmt in ("json", "human"):
                with self.subTest(format=fmt):
                    result = subprocess.run([sys.executable, "-B", str(HERE / "lint.py"), str(safe), "--format", fmt],
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, text=True, timeout=20, check=False)
                    self.assertEqual(0, result.returncode, result.stderr)
                    if fmt == "json":
                        report = json.loads(result.stdout)
                        self.assertEqual(0, report["counts"]["patterns"])
                        self.assertTrue(report["semantic_review_required"])
                        self.assertIn("nonnumeric", " ".join(report["manual_review"]))
                    else:
                        self.assertIn("manual review required even with zero warnings", result.stdout)
            self.assertEqual(before, safe.read_bytes())
            self.assertEqual(["CLAUDE.md"], sorted(p.name for p in root.iterdir()))

    def test_sensitive_and_missing_refused(self):
        with tempfile.TemporaryDirectory(prefix="doctor-refuse-") as folder:
            root = Path(folder)
            sensitive = root / ".env"
            sensitive.write_text("synthetic sensitive marker", encoding="utf-8")
            report = lint.lint_paths([sensitive, root / "absent.md"])
            self.assertEqual([], report["files"])
            self.assertEqual(2, report["counts"]["read_errors"])
            proc = subprocess.run([sys.executable, "-B", str(HERE / "lint.py"), str(root / "absent.md")],
                                  creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, timeout=20, check=False)
            self.assertEqual(2, proc.returncode)

    def test_receipts_do_not_make_scanner_semantic(self):
        # Current receipts and directives remain visible review leads. Do not
        # manufacture passing scores with an exemption keyed to these phrases.
        self.assertIn("unverified-mutable-memory", self.patterns(
            "Current receipt: revenue 7,340 AUD. Source close.csv, same frozen period and coverage.", "MEMORY.md"))
        self.assertEqual(set(), self.patterns("Pipeline status remains running. Choose yesterday's partition.", "MEMORY.md"))
        self.assertEqual([], lint.scan_text(lint.MINIMAL_FIX, "AGENTS.md", CHECKS, True)["findings"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
