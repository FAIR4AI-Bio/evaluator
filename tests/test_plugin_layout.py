#!/usr/bin/env python
"""Tests for the plugin packaging (Claude Code + vendor-neutral Agent Plugins 1.0).

What is checked:
  - the root `plugin.json` follows the Agent Plugins 1.0 manifest rules (exact `$schema`,
    closed set of top-level keys, valid plugin name);
  - `plugin.json`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` agree on
    the plugin name and carry the version in `VERSION.txt`, and `CITATION.cff`/`.zenodo.json`
    carry the matching `v<version>` tag;
  - every `skills/<name>/SKILL.md` has Agent Skills frontmatter (`name` == folder, a non-empty
    `description`, and only spec fields) between bare `---` lines, with LF endings and no BOM,
    and the old `.claude/skills/` location is gone;
  - no skill reaches bundled files through the working directory (`python scripts/...`,
    `.claude/skills/...`), since installed plugins run from the user's project folder;
  - every skill that runs a bundled script states the interpreter fallbacks (`py -3` on
    Windows, `python3` on Linux/macOS);
  - no tracked file is extensionless apart from `LICENSE` (Gemini's skill uploader rejects
    them, which is why the version lives in `VERSION.txt`).

Run (stdlib only, no pip):
    python -m unittest discover -s tests
"""
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent
SKILLS_DIR = AGENT_DIR / "skills"

sys.path.insert(0, str(AGENT_DIR / "scripts"))
import fair4ai_version as version  # noqa: E402

PLUGIN_NAME = "fair4ai-evaluator"
AGENT_PLUGINS_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AGENT_PLUGINS_KEYS = {"$schema", "name", "version", "description", "author", "homepage",
                      "repository", "license", "keywords", "extensions"}
AGENT_SKILLS_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
EXPECTED_SKILLS = {"retrieve-metadata", "evaluate-dataset", "fair4ai-scoring",
                   "batch-evaluate-datasets", "summarize-outputs"}


def load_json(rel):
    return json.loads((AGENT_DIR / rel).read_text(encoding="utf-8"))


def frontmatter(skill_md):
    """Return the top-level `key: value` pairs of a SKILL.md YAML frontmatter block.

    Reads raw bytes, so a BOM or CRLF line endings (which strict harness parsers reject) fail
    the match instead of being normalized away.
    """
    text = skill_md.read_bytes().decode("utf-8")
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None
    return dict(re.findall(r"(?m)^([A-Za-z][\w-]*):[ \t]*(.*)$", m.group(1)))


class ManifestTest(unittest.TestCase):
    def test_agent_plugins_manifest(self):
        manifest = load_json("plugin.json")
        self.assertEqual(manifest["$schema"], AGENT_PLUGINS_SCHEMA)
        self.assertLessEqual(set(manifest), AGENT_PLUGINS_KEYS)
        name = manifest["name"]
        self.assertRegex(name, r"^[a-z0-9]([a-z0-9.-]{0,62}[a-z0-9])?$")
        self.assertNotIn("--", name)
        self.assertNotIn("..", name)
        if "author" in manifest:
            self.assertLessEqual(set(manifest["author"]), {"name", "email", "url"})

    def test_manifests_agree_with_version_file(self):
        current = version.get_version()
        marketplace = load_json(".claude-plugin/marketplace.json")
        entries = [p for p in marketplace["plugins"] if p["name"] == PLUGIN_NAME]
        self.assertEqual(len(entries), 1, "marketplace must list the plugin exactly once")
        self.assertEqual(entries[0]["source"], "./")
        for label, doc in [("plugin.json", load_json("plugin.json")),
                           (".claude-plugin/plugin.json", load_json(".claude-plugin/plugin.json")),
                           ("marketplace entry", entries[0])]:
            with self.subTest(manifest=label):
                self.assertEqual(doc["name"], PLUGIN_NAME)
                self.assertEqual(doc["version"], current)

    def test_release_metadata_agrees_with_version_file(self):
        tag = "v" + version.get_version()
        self.assertEqual(load_json(".zenodo.json")["version"], tag)
        cff = (AGENT_DIR / "CITATION.cff").read_text(encoding="utf-8")
        self.assertRegex(cff, r'(?m)^version: "' + re.escape(tag) + '"$')
        self.assertEqual(set(re.findall(r"/(v\d+\.\d+\.\d+)", cff)), {tag},
                         "CITATION.cff release URLs must point at the current tag")


class SkillLayoutTest(unittest.TestCase):
    def test_skills_live_under_skills_dir(self):
        found = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}
        self.assertEqual(found, EXPECTED_SKILLS)
        self.assertFalse((AGENT_DIR / ".claude" / "skills").exists(),
                         "skills moved to skills/; .claude/skills/ would shadow the plugin copies")

    def test_frontmatter_follows_agent_skills_spec(self):
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            with self.subTest(skill=skill_md.parent.name):
                fm = frontmatter(skill_md)
                self.assertIsNotNone(fm, "missing YAML frontmatter")
                self.assertEqual(fm.get("name"), skill_md.parent.name)
                self.assertTrue(fm.get("description", "").strip())
                self.assertLessEqual(set(fm), AGENT_SKILLS_KEYS)
                if "compatibility" in fm:
                    self.assertLessEqual(len(fm["compatibility"]), 500)

    def test_no_working_directory_paths(self):
        bad = re.compile(r"python3? scripts/|\.claude/skills|`python scripts")
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            with self.subTest(skill=skill_md.parent.name):
                text = skill_md.read_text(encoding="utf-8")
                self.assertEqual(bad.findall(text), [])
                self.assertIn("${CLAUDE_PLUGIN_ROOT}", text,
                              "each skill must define <PLUGIN_ROOT> in its Plugin files section")

    def test_interpreter_rule_has_platform_fallbacks(self):
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            text = " ".join(skill_md.read_text(encoding="utf-8").split())
            if 'python "<PLUGIN_ROOT>/' not in text:
                continue
            with self.subTest(skill=skill_md.parent.name):
                self.assertRegex(text, r"`py -3`,? on Windows|on Windows,? use `py -3`")
                self.assertRegex(text, r"`python3` on Linux/macOS|Linux/macOS use `python3`")


class PackagingTest(unittest.TestCase):
    def test_no_extensionless_files(self):
        out = subprocess.run(["git", "-C", str(AGENT_DIR), "ls-files"],
                             capture_output=True, text=True)
        if out.returncode != 0:
            self.skipTest("not a git checkout")
        bad = [f for f in out.stdout.splitlines()
               if "." not in Path(f).name and Path(f).name != "LICENSE"]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
