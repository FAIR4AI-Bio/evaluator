# Changelog

All notable changes to the FAIR4AI-Bio evaluator agent. The version lives in the plugin-root
`VERSION.txt` file (mirrored in the plugin manifests) and is stamped into every evaluation JSON (`session.agent_provenance`).

Versions follow [semantic versioning](https://semver.org/), applied to evaluation results:

- **MAJOR** — the checklist items or the scoring rules change, so scores are no longer comparable
  with earlier versions.
- **MINOR** — new features, or rubric/skill changes that may shift how items are rated.
- **PATCH** — bug fixes and documentation that do not change ratings or scores.

Each release is tagged `v<version>` in git.

## [0.2.1] — 2026-10-28

Cross-harness portability fixes from running the plugin in Gemini. Ratings and scores are unchanged.

- The version file is now **`VERSION.txt`** (was `VERSION`): Gemini's skill uploader rejects
  extensionless files. `scripts/fair4ai_version.py` falls back to the `version` in `plugin.json`
  if `VERSION.txt` is missing. `tests/test_plugin_layout.py` fails on any tracked extensionless
  file other than `LICENSE`.
- `.gitattributes` keeps LF line endings in every checkout, and the frontmatter test now reads
  `SKILL.md` as raw bytes, so a BOM or CRLF delimiters fail the test.
- The interpreter rule allows `python3` on Linux/macOS when `python` is not found (minimal
  containers often ship only `/usr/bin/python3`); Windows still falls back to `py -3`, never
  `python3`. A layout test checks every skill that runs a script states both fallbacks.
- `CITATION.cff` and `.zenodo.json` are part of the version bump, and a layout test checks
  that their version and release-tag URLs match `VERSION.txt`.

## [0.2.0] — 2026-10-25

Packaged as an installable plugin. The checklist, rubric and scoring are unchanged, so scores remain
comparable with 0.1.0.

- The repository is now the **`fair4ai-evaluator` plugin**. It has a Claude Code manifest
  (`.claude-plugin/plugin.json`), a one-plugin marketplace (`.claude-plugin/marketplace.json`,
  `fair4ai-bio`), and a vendor-neutral [Agent Plugins 1.0](https://agent-plugins.org/) manifest
  (`plugin.json`) for GitHub Copilot and other clients.
- Skills moved from `.claude/skills/` to `skills/`. In Claude Code they are now invoked as
  `/fair4ai-evaluator:<skill>`.
- The skills no longer depend on the working directory. They reach the bundled checklist, rubric,
  template and scripts through the plugin root (`${CLAUDE_PLUGIN_ROOT}`, or the path relative to the
  skill file in other clients), so the plugin works from any project folder. Outputs still default to
  the working directory.
- `merge_ratings.py` in `evaluate-dataset` now gets the resolved checklist path instead of a bare
  `CHECKLIST.csv`.
- Batch sub-agents receive the plugin root explicitly. The batch coordinator falls back to sequential
  evaluation in clients without sub-agents.
- `CLAUDE.md` became the tool-neutral contributor guide `AGENTS.md`. `CLAUDE.md` now imports it.
- New `tests/test_plugin_layout.py` checks the manifests (including the version against `VERSION`),
  the skill frontmatter, and that no skill uses paths relative to the working directory.

## [0.1.0] — 2026-10-25

First versioned release of the agent, as split out of the `fair4ai-eval-agent/` folder of
[FAIR4AI-checklists](https://github.com/FAIR4AI-Bio/FAIR4AI-checklists).

- 89-item FAIR4AI-Bio checklist (`CHECKLIST.csv`, 9 sections) and `RATING_RUBRIC.md`.
- Five skills: `retrieve-metadata`, `evaluate-dataset`, `fair4ai-scoring`,
  `batch-evaluate-datasets`, `summarize-outputs`.
- Deterministic two-assessment scoring (Traditional FAIR and AI-FAIR, 0–1).
- Agent versioning: `VERSION` file, `scripts/fair4ai_version.py`, and a
  `session.agent_provenance` block in every evaluation (agent version, git commit, checklist
  SHA-256, and the version that computed the scores). The compiled scores CSV gains
  `agent_version`, `scored_with_version`, and `checklist_sha256` columns, and the aggregates flag
  runs that mix agent or checklist versions.
