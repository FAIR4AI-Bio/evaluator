# Changelog

All notable changes to the FAIR4AI-Bio evaluator agent. The version lives in the repo-root
`VERSION` file and is stamped into every evaluation JSON (`session.agent_provenance`).

Versions follow [semantic versioning](https://semver.org/), applied to evaluation results:

- **MAJOR** — the checklist items or the scoring rules change, so scores are no longer comparable
  with earlier versions.
- **MINOR** — new features, or rubric/skill changes that may shift how items are rated.
- **PATCH** — bug fixes and documentation that do not change ratings or scores.

Each release is tagged `v<version>` in git.

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
