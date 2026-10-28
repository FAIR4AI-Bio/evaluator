#!/usr/bin/env python
"""Tests for agent versioning: the VERSION.txt file and the `session.agent_provenance` stamp.

What is checked:
  - VERSION.txt holds a semantic version (MAJOR.MINOR.PATCH) with a matching CHANGELOG.md entry,
    and the version falls back to plugin.json when VERSION.txt is missing;
  - the checklist fingerprint ignores line endings (CRLF and LF checkouts agree);
  - END TO END through the real CLIs (scaffold -> merge with --session-json -> score ->
    compile): the scaffold stamps agent version, git commit and checklist SHA-256; the
    agent's session file can neither drop nor forge that stamp; the scorer adds
    `scored_with_*`; and the compiled CSV/aggregates carry the version columns;
  - an evaluation that predates versioning is scored with a warning and its unknown
    fields are recorded as null, not guessed.

Run (stdlib only, no pip):
    python -m unittest discover -s tests
"""
import csv
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

AGENT_DIR = Path(__file__).resolve().parent.parent
CHECKLIST = AGENT_DIR / "CHECKLIST.csv"
SCRIPTS = AGENT_DIR / "scripts"

sys.path.insert(0, str(SCRIPTS))
import fair4ai_version as version  # noqa: E402


def run_script(name, *args):
    """Run a helper script exactly as the skills do; return the CompletedProcess."""
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", check=True)


class VersionFileTest(unittest.TestCase):
    def test_version_is_semver(self):
        self.assertRegex(version.get_version(), r"^\d+\.\d+\.\d+$")

    def test_changelog_has_entry_for_current_version(self):
        changelog = (AGENT_DIR / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(changelog, r"(?m)^## \[" + re.escape(version.get_version()) + r"\]")

    def test_version_falls_back_to_plugin_manifest(self):
        manifest = json.loads((AGENT_DIR / "plugin.json").read_text(encoding="utf-8"))
        with mock.patch.object(version, "VERSION_FILE", str(AGENT_DIR / "no-such-file.txt")):
            self.assertEqual(version.get_version(), manifest["version"])

    def test_checklist_fingerprint_ignores_line_endings(self):
        with tempfile.TemporaryDirectory() as d:
            lf, crlf = Path(d, "lf.csv"), Path(d, "crlf.csv")
            lf.write_bytes(b"Item,Note\nA,x\n")
            crlf.write_bytes(b"Item,Note\r\nA,x\r\n")
            self.assertEqual(version.checklist_sha256(lf), version.checklist_sha256(crlf))
            self.assertIsNone(version.checklist_sha256(Path(d, "missing.csv")))


class ProvenanceEndToEndTest(unittest.TestCase):
    """scaffold -> merge (agent session) -> score -> compile, via the real command lines."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.results = Path(cls.tmp.name, "evaluation_results")
        cls.results.mkdir()
        cls.eval_json = cls.results / "FAIR4AI_eval_demo_2026-01-01_000000.json"
        run_script("build_response_scaffold.py", "--checklist", CHECKLIST, "--out", cls.eval_json)
        cls.scaffold_prov = json.loads(cls.eval_json.read_text(encoding="utf-8"))["session"][
            version.PROVENANCE_KEY]

        # The agent's session file has no provenance block of its own, plus a forged one would
        # be ignored: only the scripts write agent_provenance.
        session = Path(cls.tmp.name, "session.json")
        session.write_text(json.dumps({"evaluation_date": "2026-01-01",
                                       "dataset": {"title": "Demo"},
                                       version.PROVENANCE_KEY: {"agent_version": "forged"}}),
                           encoding="utf-8")
        run_script("merge_ratings.py", "--scaffold", cls.eval_json, "--session-json", session)
        run_script("compute_fair4ai_scores.py", cls.eval_json)
        cls.doc = json.loads(cls.eval_json.read_text(encoding="utf-8"))
        cls.prov = cls.doc["session"][version.PROVENANCE_KEY]

        cls.csv_path = Path(cls.tmp.name, "scores.csv")
        out = run_script("compile_fair4ai_results.py", "--results-dir", cls.results,
                         "--out-csv", cls.csv_path).stdout
        cls.agg = json.loads(next(l for l in out.splitlines() if l.startswith("AGG:"))[4:])

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_scaffold_stamps_version_commit_and_checklist(self):
        p = self.scaffold_prov
        self.assertEqual(list(p), version.SCAFFOLD_FIELDS)
        self.assertEqual(p["agent_version"], version.get_version())
        self.assertEqual(p["checklist_file"], "CHECKLIST.csv")
        self.assertEqual(p["checklist_sha256"], version.checklist_sha256(CHECKLIST))
        if version.get_git_commit():  # a source archive without .git records null
            self.assertRegex(p["git_commit"], r"^[0-9a-f]{40}$")

    def test_session_merge_keeps_stamp_and_rejects_forgery(self):
        self.assertEqual(self.doc["session"]["dataset"]["title"], "Demo")
        self.assertEqual(self.prov["agent_version"], version.get_version())
        for key in version.SCAFFOLD_FIELDS:
            self.assertEqual(self.prov[key], self.scaffold_prov[key], key)

    def test_scorer_records_its_version(self):
        self.assertEqual(self.prov["scored_with_version"], version.get_version())
        self.assertEqual(self.prov["scored_with_commit"], version.get_git_commit())
        self.assertTrue(self.doc["summary"]["fair4ai_scores"])

    def test_compiled_csv_and_aggregates_carry_version(self):
        with open(self.csv_path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["agent_version"], version.get_version())
        self.assertEqual(rows[0]["scored_with_version"], version.get_version())
        self.assertEqual(rows[0]["checklist_sha256"], self.prov["checklist_sha256"][:12])
        self.assertEqual(self.agg["by_agent_version"], {version.get_version(): ["demo"]})
        self.assertFalse(self.agg["mixed_versions"])


class UnversionedEvaluationTest(unittest.TestCase):
    def test_legacy_eval_gets_null_fields_and_a_warning(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "legacy.json")
            path.write_text(json.dumps({
                "session": {"evaluation_date": "2025-01-01"},
                "responses": [{"item": "A", "status": "meets", "fair_category": "Findable",
                               "ai_fair_criteria": "Structural"}],
            }), encoding="utf-8")
            proc = run_script("compute_fair4ai_scores.py", path)
            self.assertIn("agent_version is missing", proc.stderr)
            prov = json.loads(path.read_text(encoding="utf-8"))["session"][version.PROVENANCE_KEY]
            for key in version.SCAFFOLD_FIELDS:
                self.assertIsNone(prov[key], key)
            self.assertEqual(prov["scored_with_version"], version.get_version())

    def test_dry_run_does_not_stamp(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, "legacy.json")
            original = json.dumps({"session": {}, "responses": []})
            path.write_text(original, encoding="utf-8")
            run_script("compute_fair4ai_scores.py", path, "--dry-run")
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
