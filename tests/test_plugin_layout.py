#!/usr/bin/env python
"""Tests for the plugin packaging (Claude Code + vendor-neutral Agent Plugins 1.0).

What is checked:
  - the root `plugin.json` follows the Agent Plugins 1.0 manifest rules (exact `$schema`,
    closed set of top-level keys, valid plugin name);
  - `plugin.json`, `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` agree on
    the plugin name and carry the version in `VERSION`;
  - every `skills/<name>/SKILL.md` has Agent Skills frontmatter (`name` == folder, a non-empty
    `description`, and only spec fields), and the old `.claude/skills/` location is gone;
  - no skill reaches bundled files through the working directory (`python scripts/...`,
    `.claude/skills/...`), since installed plugins run from the user's project folder.

Run (stdlib only, no pip):
    python -m unittest discover -s tests
"""
import json
import re
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
    """Return the top-level `key: value` pairs of a SKILL.md YAML frontmatter block."""
    text = skill_md.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
