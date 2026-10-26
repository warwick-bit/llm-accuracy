"""Portable workflow contracts: scope, honest coverage and stale proposals."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import doctor

HERE = Path(__file__).resolve().parent


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="doctor-workflow-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "CLAUDE.md").write_bytes(b"Keep source context.\r\nPreserve backups.\r\n")
        (self.root / "settings.json").write_text(json.dumps({"env": {"PRIVATE_VALUE": "synthetic-private-payload"}, "model": "example-model", "hooks": {"PreToolUse": [{"hooks": [{"command": "never execute this private command"}]}]}}), encoding="utf-8")
        manifest = {"schema": 1, "client": "claude", "profile": "isolated example", "problem": "Review scope and recovery", "files": [
            {"id": "core", "path": "CLAUDE.md", "role": "instructions", "consumer": "unknown"},
            {"id": "settings", "path": "settings.json", "role": "settings", "consumer": "selected user config, not exercised"}]}
        self.manifest = self.root / "manifest.json"
        self.write(self.manifest, manifest)
        self.packet = doctor.prepare(self.manifest, self.root / "audit")
        self.review = json.loads((self.root / "audit/assessment-template.json").read_text())
        self.review.update(reviewer="Synthetic contract fixture", summary="Policy is scoped; execution remains unverified", reviewed_files=["core", "settings"], findings=[{
            "id": "CONTROL", "source_id": "core", "classification": "observed wording", "recommendation": "RETAIN", "summary": "Keep backups", "evidence": "Core line 2 requires backups", "check": "Exercise actual write/rollback separately"}])
        for item in self.review["fidelity_coverage"].values():
            item.update(evidence="This fixture supplies context/backups only; fidelity behavior is unverified", check="Exercise a scoped supported answer and unsupported assertion in a disposable consumer")

    def write(self, path, value):
        path.write_text(json.dumps(value), encoding="utf-8")

    def render(self, review=None):
        path = self.root / "assessment.json"
        self.write(path, self.review if review is None else review)
        return doctor.render(self.root / "audit/audit.json", path)

    def test_quiet_sources_still_need_complete_review(self):
        self.assertEqual(self.packet["sources"][0]["lexical_leads"], [])
        self.assertIn("UNVERIFIED", self.render())
        partial = copy.deepcopy(self.review)
        partial["reviewed_files"] = ["core"]
        with self.assertRaisesRegex(ValueError, "Every supplied file"):
            self.render(partial)
        partial["unreviewed_files"] = [{"id": "settings", "reason": "Consumer receipt missing; structural summary not reviewed"}]
        self.assertIn("Unread inputs", self.render(partial))
        partial["unreviewed_files"].append({"id": "unsupplied-reference", "reason": "Mentioned by instructions but outside the authorized packet"})
        with self.assertRaises(ValueError):
            self.render(partial)

    def test_settings_values_not_copied_or_executed(self):
        for path in (self.root / "audit").iterdir():
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("synthetic-private-payload", text)
            self.assertNotIn("never execute this private command", text)
        summary = self.packet["sources"][1]["summary"]
        self.assertEqual(summary["hook_groups"], {"PreToolUse": 1})
        self.assertEqual(summary["environment_keys"], ["PRIVATE_VALUE"])

    def test_hook_and_plugin_scripts_are_inert_bound_sources(self):
        marker = self.root / "executed.txt"
        text = 'const prompt = "Preserve source context.";\nrequire("node:fs").writeFileSync(' + json.dumps(str(marker)) + ', "unexpected");\n'
        for suffix in (".ts", ".js", ".mjs", ".cjs"):
            for role in ("instructions", "launcher"):
                with self.subTest(suffix=suffix, role=role):
                    source = self.root / ("plugin" + suffix)
                    source.write_text(text, encoding="utf-8")
                    self.write(self.manifest, {"schema": 1, "client": "claude", "profile": "synthetic", "problem": "Review plugin source, never execute", "files": [
                        {"id": "script", "path": source.name, "role": role, "consumer": "source only; loading unknown"}]})
                    output = self.root / (role + suffix + "-audit")
                    packet = doctor.prepare(self.manifest, output)
                    self.assertEqual(packet["sources"][0]["text"], text)
                    review = copy.deepcopy(self.review)
                    review.update(audit_id=packet["audit_id"], reviewed_files=["script"])
                    review["findings"][0].update(source_id="script", evidence="Script line 1 preserves source context")
                    assessment = self.root / "script-assessment.json"
                    self.write(assessment, review)
                    self.assertIn("script", doctor.render(output / "audit.json", assessment))
                    self.assertFalse(marker.exists())
                    source.write_text(text + "// changed\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Source changed"):
                        doctor.render(output / "audit.json", assessment)
        # New source suffixes do not relax sensitive-input or credential refusal.
        with self.assertRaisesRegex(ValueError, "Sensitive input"):
            doctor.safe_file(self.root / ".credentials.json", "launcher")
        binary = self.root / "plugin.exe"
        binary.write_bytes(b"synthetic")
        with self.assertRaisesRegex(ValueError, "Unsupported input"):
            doctor.safe_file(binary, "launcher")
        source.write_text("sk-" + "A" * 24, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Possible credential"):
            doctor.prepare(self.manifest, self.root / "credential-audit")

    def test_omitted_setting_values_cannot_identify_permission_mode(self):
        summaries = [doctor.settings_summary("claude", json.dumps({"skipDangerousModePermissionPrompt": flag})) for flag in (False, True)]
        self.assertEqual(summaries[0], summaries[1])
        self.assertFalse(summaries[0]["permissions_present"])
        mode_summaries = [doctor.settings_summary("claude", json.dumps({"permissions": {"defaultMode": mode}})) for mode in ("default", "bypassPermissions")]
        self.assertEqual(mode_summaries[0], mode_summaries[1])
        self.assertTrue(mode_summaries[0]["permissions_present"])
        self.assertNotIn("bypassPermissions", json.dumps(mode_summaries[0]))

    def test_real_cli_flags_are_not_credential_strings(self):
        text = "codex --ask-for-approval never\n# sandbox|ask-for-approval policy"
        self.assertEqual(doctor.safe_text(text), text)
        with self.assertRaisesRegex(ValueError, "credential material"):
            doctor.safe_text('api key: ' + 'sk-' + 'SyntheticPrivateToken123456789')

    def test_credential_like_file_id_gets_safe_actionable_cli_error(self):
        manifest = doctor.read_json(self.manifest)
        bad_id = "sk-pr-review-loop"
        manifest["files"][0].update(id=bad_id)
        self.write(self.manifest, manifest)
        output = self.root / "id-audit"
        command = [sys.executable, "-B", str(HERE / "doctor.py"), "prepare", str(self.manifest), "--out", str(output)]
        refused = subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("File ID at manifest entry 1 resembles a credential", refused.stderr)
        self.assertIn("skill-review", refused.stderr)
        self.assertNotIn(bad_id, refused.stderr)
        self.assertFalse(output.exists())
        manifest["files"][0].update(id="skill-review", path="CLAUDE.md")
        self.write(self.manifest, manifest)
        accepted = subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(doctor.read_json(output / "audit.json")["sources"][0]["id"], "skill-review")

    def test_private_key_rule_source_is_not_key_material(self):
        rule = r"$Content -match '(?s)-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\s+[A-Za-z0-9+/=\s]{64,}-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'"
        self.assertEqual(doctor.safe_text(rule), rule)
        for label in ("", "RSA ", "EC ", "OPENSSH ", "ENCRYPTED "):
            with self.subTest(label=label):
                header = "-----BEGIN " + label + "PRIVATE KEY-----"
                with self.assertRaisesRegex(ValueError, "credential material"):
                    doctor.safe_text('key = "' + header + '"')

    def test_exact_proposal_and_source_binding(self):
        change = self.review["findings"][0]
        change.update(recommendation="NARROW", proposal={"line": 1, "end_line": 1, "old_text": "Keep source context.", "new_text": "Keep relevant source context.", "rollback": "Restore if required context is lost"})
        self.assertIn("Proposal HYPOTHESIS", self.render())
        change["proposal"]["old_text"] = "unmatched old text"
        with self.assertRaisesRegex(ValueError, "exact source span"):
            self.render()
        change["proposal"]["old_text"] = "Keep source context."
        (self.root / "CLAUDE.md").write_text("Changed concurrently", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Source changed"):
            self.render()

    def test_fidelity_coverage_cannot_silently_omit_a_risk(self):
        risk = "unsupported_extra_claims"
        self.review["fidelity_coverage"][risk].update(status="NOT_FOUND", evidence="Neither supplied source protects extra factual claims")
        self.assertIn(risk + " — NOT_FOUND", self.render())
        omitted = copy.deepcopy(self.review)
        del omitted["fidelity_coverage"][risk]
        with self.assertRaisesRegex(ValueError, "every fidelity risk"):
            self.render(omitted)
        omitted["fidelity_coverage"][risk] = {"status": "UNVERIFIED", "source_ids": [], "evidence": "", "check": ""}
        with self.assertRaisesRegex(ValueError, "every fidelity risk"):
            self.render(omitted)
        invalid = copy.deepcopy(self.review)
        invalid["fidelity_coverage"][risk]["status"] = "PASS"
        with self.assertRaisesRegex(ValueError, "Invalid fidelity status"):
            self.render(invalid)

    def test_fidelity_protection_needs_reviewed_evidence_and_honest_scope(self):
        (self.root / "CLAUDE.md").write_text("Every factual claim must have supporting evidence.\nPreserve backups.\n", encoding="utf-8")
        packet = doctor.prepare(self.manifest, self.root / "general-rule-audit")
        self.write(self.root / "audit/audit.json", packet)
        self.review["audit_id"] = packet["audit_id"]
        item = self.review["fidelity_coverage"]["unsupported_extra_claims"]
        # Evidence transport only: the semantic judgment is a supplied fixture.
        item.update(status="PROTECTION_FOUND", source_ids=["core"], evidence="Core line 1: Every factual claim must have supporting evidence. This broad rule also covers supplementary claims; effectiveness unverified")
        self.assertIn("PROTECTION_FOUND", self.render())
        item["status"] = "PARTIAL"
        self.assertIn("— PARTIAL", self.render())
        item["source_ids"] = []
        with self.assertRaisesRegex(ValueError, "reviewed source reference"):
            self.render()
        item["source_ids"] = ["not-supplied"]
        with self.assertRaisesRegex(ValueError, "reviewed source IDs"):
            self.render()
        self.review["reviewed_files"] = ["core"]
        self.review["unreviewed_files"] = [{"id": "settings", "reason": "Not assessed in partial fixture"}]
        item.update(status="NOT_FOUND", source_ids=[])
        with self.assertRaisesRegex(ValueError, "Unread scope"):
            self.render()
        item["status"] = "UNVERIFIED"
        self.assertIn("— UNVERIFIED", self.render())

    def test_addition_preserves_an_exact_anchor_and_does_not_edit(self):
        original = (self.root / "CLAUDE.md").read_bytes()
        finding = self.review["findings"][0]
        finding.update(recommendation="ADD", classification="policy gap", summary="Cover supplementary factual claims", proposal={"line": 2, "end_line": 2, "old_text": "Preserve backups.", "position": "after", "new_text": "Support supplementary factual claims too.", "rollback": "Remove this addition if it blocks supported derivations"})
        for position in ("before", "after"):
            with self.subTest(position=position):
                finding["proposal"]["position"] = position
                self.assertIn("anchor stays unchanged", self.render())
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), original)
        for field, value, message in (("old_text", "missing anchor", "exact source span"), ("position", "replace", "one unchanged anchor"), ("new_text", " ", "one unchanged anchor")):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.review)
                invalid["findings"][0]["proposal"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    self.render(invalid)
        finding.update(source_id="settings")
        with self.assertRaisesRegex(ValueError, "text-source"):
            self.render()

    def test_target_context_and_legacy_packet_are_explicit(self):
        self.assertIn("model: unknown", self.render())
        manifest = json.loads(self.manifest.read_text())
        manifest["target"] = {"model": "selected-model", "client_version": "owner-reported", "working_directory": "D:/isolated/example"}
        self.write(self.manifest, manifest)
        packet = doctor.prepare(self.manifest, self.root / "with-target")
        self.assertEqual(packet["target"]["model"], "selected-model")
        self.assertEqual(packet["target"]["effort"], "unknown")
        manifest["target"]["discover_home"] = "never"
        self.write(self.manifest, manifest)
        with self.assertRaisesRegex(ValueError, "Target accepts only"):
            doctor.prepare(self.manifest, self.root / "bad-target")
        legacy = copy.deepcopy(self.packet)
        del legacy["audit_id"]
        legacy["schema"] = 1
        for key in ("target", "fidelity_risks"):
            del legacy[key]
        legacy["audit_id"] = doctor.sha(doctor.canonical(legacy))
        self.write(self.root / "audit/audit.json", legacy)
        self.review["audit_id"] = legacy["audit_id"]
        del self.review["fidelity_coverage"]
        self.assertIn("Legacy schema-1 audit", self.render())

    def test_mixed_packet_and_sensitive_scope_refused(self):
        wrong = copy.deepcopy(self.review)
        wrong["audit_id"] = "other audit"
        with self.assertRaisesRegex(ValueError, "another audit"):
            self.render(wrong)
        blocked = self.root / "auth.json"
        blocked.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Sensitive input"):
            doctor.safe_file(blocked, "receipt")
        manifest = json.loads(self.manifest.read_text())
        manifest["files"][0]["path"] = "."
        self.write(self.manifest, manifest)
        with self.assertRaises(ValueError):
            doctor.prepare(self.manifest, self.root / "refused")
        self.assertFalse((self.root / "refused").exists())

    def test_cli_consumer_and_no_overwrite(self):
        # The actual prepared consumer must receive the current audit guidance,
        # including long-session evidence limits; this proves delivery, not efficacy.
        prepared_prompt = (self.root / "audit/prompt.md").read_text(encoding="utf-8")
        guidance = (HERE / "DOCTOR-PROMPT.md").read_text(encoding="utf-8")
        self.assertTrue(prepared_prompt.startswith(guidance + "\n\n"))
        assessment = self.root / "assessment.json"
        self.write(assessment, self.review)
        output = self.root / "report.md"
        command = [sys.executable, "-B", str(HERE / "doctor.py"), "report", str(self.root / "audit/audit.json"), str(assessment), "--out", str(output)]
        run = subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
        before = output.read_bytes()
        self.assertEqual(subprocess.run(command, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0, capture_output=True, timeout=20).returncode, 2)
        self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
