# AI-FAIR Dataset Evaluation Agent (`evaluator`) [![DOI](https://zenodo.org/badge/1419294252.svg)](https://doi.org/10.5281/zenodo.23744163)


Repository for the FAIR4AI evaluation agentic workflow, maintained by the [FAIR4AI-Bio](https://github.com/FAIR4AI-Bio) working group.

An AI agent that evaluates biodiversity, ecology, and environmental science datasets for AI-readiness using the **FAIR4AI-Bio checklist**. The agent reads a dataset's landing page or local metadata files, rates each of the 89 checklist items as *meets / partial / does not meet / N/A* (judged against each item's `Requirement Definition` and the section-level guidance in `RATING_RUBRIC.md`), and produces a structured JSON report with **two reproducible assessments** — **Traditional FAIR** (Findable, Accessible, Interoperable, Reusable + an overall) and **AI-FAIR** (ML-ready, AI-ready for task, Traceable, CARE compliance + an overall) — each score in **0–1, where 1 is "most FAIR4AI"**, computed by the `fair4ai-scoring` skill.

The core thesis: **FAIR compliance is necessary but not sufficient for AI-ready data.** Reporting FAIR and AI-FAIR side by side makes that gap measurable.

See `example_outputs/` for complete evaluation reports for two example datasets — a NEON observational dataset (ground beetles) and the TreeOfLife-200M image corpus (Hugging Face).

---

## Requirements

- A dataset source: URL to a landing page, or a local directory containing metadata files (JSON-LD, EML, DataCite XML, README, etc.)
- An agent harness that can load the plugin: [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (primary target), or another client that supports [Agent Plugins](https://agent-plugins.org/) / [Agent Skills](https://agentskills.io/) such as GitHub Copilot
- `python` 3 on the `PATH` (the scripts are stdlib-only; nothing to `pip install` except for the optional figure)

---

## Setup

The evaluator is packaged as the **`fair4ai-evaluator` plugin**. Install it once, then use it from
any project folder. Evaluation outputs (run folders) are written to your working directory, not
into the plugin.

### Claude Code

```
/plugin marketplace add FAIR4AI-Bio/evaluator
/plugin install fair4ai-evaluator@fair4ai-bio
```

Then, in any project:

```
/fair4ai-evaluator:evaluate-dataset
```

The agent will prompt you for the dataset source and other parameters. Press Enter to accept defaults for optional parameters.

### GitHub Copilot and other Agent Plugins clients

The repository root is also a portable [Agent Plugins 1.0](https://agent-plugins.org/specification)
package (`plugin.json` + `skills/<name>/SKILL.md`). Install it with your client's plugin command
(for the Copilot CLI: `copilot plugin install FAIR4AI-Bio/evaluator`), or point a client that reads
[Agent Skills](https://agentskills.io/) at the `skills/` directory. When a client does not expand
Claude Code's `${CLAUDE_PLUGIN_ROOT}`, the skills resolve their bundled files (checklist, rubric,
scripts) relative to their own location. The batch coordinator falls back to evaluating datasets one
at a time when the client has no sub-agents.

### Developing the plugin

```bash
git clone https://github.com/FAIR4AI-Bio/evaluator.git
cd evaluator
claude --plugin-dir .
```

`--plugin-dir` loads your working tree as the plugin for that session. See `AGENTS.md` for the
contributor guide.

---

## Batch evaluation

To evaluate **many datasets at once**, use the `batch-evaluate-datasets` skill:

```
/fair4ai-evaluator:batch-evaluate-datasets
```

It reads a **flexible dataset list** — a `.txt`, `.csv`, or `.md` file — parses out each dataset and its URL regardless of layout, and normalizes it into a standard CSV (`email,name,dataset_short_name,url,notes`). It then coordinates **one sub-agent per dataset in parallel** (launched in waves of 5 by default), each running the `evaluate-dataset` workflow non-interactively, and finally **hands off to the `summarize-outputs` skill** for the scores CSV, figure, and report. The default sub-agent model is **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`); the skill asks whether to use it or a different model.

Every artifact of a run is written into one self-contained **run folder** (default `batch_run_<date>/`):

```
batch_run_<date>/
  batch_datasets_<date>.csv               # normalized reference list (from any input format)
  batch_evaluate_progress.md              # resumable progress tracker
  confidence_map.json
  retrieved_metadata/<short_name>/        # cached metadata per dataset (from retrieve-metadata)
  evaluation_results/FAIR4AI_eval_<short_name>_<YYYY-MM-DD_HHMMSS>.json  # one full 89-item evaluation per dataset
  fair4ai_scores_summary_<date>.csv       # compiled per-dataset scores + status counts
  fair4ai_score_distributions_<date>.{png,pdf,svg}   # summary figure
  FAIR4AI_summary_report_<date>.md        # cross-dataset narrative report
```

The run is **resumable** — re-invoking the skill on an existing run folder reads `batch_evaluate_progress.md` and re-runs only the datasets that are still pending or failed. Evaluation filenames carry a timestamp to the second, so re-runs of a dataset never collide; `summarize-outputs` keeps only the newest run of each dataset by default. The summary **figure** needs `numpy` + `matplotlib` (`pip install -r <plugin dir>/scripts/requirements-viz.txt`); if they're absent the figure is skipped and the CSV + report are still produced (scoring and compilation are stdlib-only).

---

## How the plugin files work

- **`.claude-plugin/plugin.json`** — the Claude Code plugin manifest; **`.claude-plugin/marketplace.json`** lists this repository as a one-plugin marketplace (`fair4ai-bio`).
- **`plugin.json`** — the vendor-neutral [Agent Plugins](https://agent-plugins.org/) manifest read by other clients (e.g. GitHub Copilot).
- **`skills/retrieve-metadata/SKILL.md`** — the `retrieve-metadata` skill: fetches a dataset's metadata (URL or local path) and, by default, saves it under `retrieved_metadata/<short_name>/` so it can be reused without re-fetching. Called on its own or internally by `evaluate-dataset`.
- **`skills/evaluate-dataset/SKILL.md`** — the `evaluate-dataset` skill. Establishes a run folder, skips datasets already evaluated (unless a re-run is requested), looks for already-downloaded metadata before calling `retrieve-metadata`, rates each item, builds the output JSON, and computes scores.
- **`RATING_RUBRIC.md`** — the authority for how each item's `meets / partial / does not meet / N/A` status is chosen (including the N/A rule).
- **`skills/fair4ai-scoring/SKILL.md`** + **`scripts/compute_fair4ai_scores.py`** — the skill and deterministic tool that compute `summary.fair4ai_scores` (0–1) from the per-item statuses: Traditional FAIR from each item's `FAIR category`, and AI-FAIR from each item's `AI FAIR Criteria` value.
- **`skills/batch-evaluate-datasets/SKILL.md`** — the `batch-evaluate-datasets` **coordinator** skill: reads a dataset list and orchestrates parallel per-dataset sub-agents (reusing `evaluate-dataset` in Batch / non-interactive mode), then hands off to `summarize-outputs` for the CSV, figure, and report.
- **`skills/summarize-outputs/SKILL.md`** — the `summarize-outputs` skill: compiles any directory of evaluation JSONs into a scores CSV, summary figure, and narrative report (via `scripts/compile_fair4ai_results.py` and `scripts/make_fair4ai_figure.py`); keeps only the newest run of each dataset by default.

All five capabilities live under `skills/` (one skill per directory, each with a `SKILL.md`). In Claude Code they are namespaced by the plugin name, e.g. `/fair4ai-evaluator:evaluate-dataset`. The skills locate the bundled checklist, rubric, and scripts through the plugin root, so they work from any working directory. To change agent behavior, edit these files and load your working tree with `claude --plugin-dir .`.

---

## Versioning

The agent is versioned with [semantic versioning](https://semver.org/). The current version is in the
plugin-root **`VERSION.txt`** file (print it with `python scripts/fair4ai_version.py`), mirrored in the
`version` field of the plugin manifests;
each release is tagged `v<version>` in git, and **`CHANGELOG.md`** lists what changed. A **MAJOR**
bump means the checklist items or scoring rules changed, so scores are no longer comparable with
earlier versions; **MINOR** covers new features or rubric/skill changes that may shift ratings;
**PATCH** covers fixes and documentation.

Every evaluation records which version produced it in `session.agent_provenance`:

```json
"agent_provenance": {
  "agent_version": "0.1.0",
  "git_commit": "<full commit of the plugin, or null if it is not a git checkout>",
  "git_dirty": false,
  "checklist_file": "CHECKLIST.csv",
  "checklist_sha256": "<fingerprint of the checklist used>",
  "scored_with_version": "0.1.0",
  "scored_with_commit": "<commit of the scorer>"
}
```

The scripts fill this in, not the AI model: `build_response_scaffold.py` stamps the first five
fields, `merge_ratings.py` keeps them when the session block is replaced, and
`compute_fair4ai_scores.py` adds `scored_with_*`. The checklist fingerprint ignores line endings, so
Windows and Linux checkouts of the same checklist match. Evaluations made before versioning have no
stamp; re-scoring one warns and records the unknown fields as `null`. The compiled scores CSV has
`agent_version`, `scored_with_version` and `checklist_sha256` columns, and `summarize-outputs` flags
any run that mixes agent or checklist versions.

---

## Output format

The JSON report has three top-level sections:

- **`session`** — evaluation date, AI model, metadata sources used, dataset identity (title, DOI, landing page URL, citation), evaluator information, and `agent_provenance` (agent version, git commit, checklist fingerprint; see [Versioning](#versioning))
- **`responses`** — one object per checklist item with `item`, `requirement_definition`, `status` (`meets` / `partial` / `does not meet` / `N/A`), `evidence`, `notes`, `recommendation`, `fair_category` (the FAIR dimension(s) the item counts toward), and `ai_fair_criteria` (the Structural/Scientific/Provenance/Governance facet(s) it counts toward)
- **`summary`** — `strengths`, `gaps`, `overall_assessment` (2–3 sentence narrative), and `fair4ai_scores` (two nested blocks — `traditional_fair` and `ai_fair`, each with an overall score in 0–1 and per-dimension/per-facet `details`/`components` counts) computed by the `fair4ai-scoring` skill

Output filename convention: `FAIR4AI_eval_<short_name>_<YYYY-MM-DD_HHMMSS>.json` (timestamp to the second, so re-runs of a dataset never collide). Single runs write it to `<output dir>/fair4ai_run_<TS>/evaluation_results/`.

See `example_outputs/` for complete examples.

---

## Files in this repository

| File | Description |
|------|-------------|
| `.claude-plugin/plugin.json` | Claude Code plugin manifest (`fair4ai-evaluator`) |
| `.claude-plugin/marketplace.json` | One-plugin marketplace (`fair4ai-bio`) so Claude Code can install from this repository |
| `plugin.json` | Vendor-neutral Agent Plugins 1.0 manifest (GitHub Copilot and other clients) |
| `AGENTS.md` | Contributor guide for developing the plugin (read by most coding agents) |
| `CLAUDE.md` | Imports `AGENTS.md` plus Claude Code–specific development notes (for contributors; not loaded for plugin users) |
| `skills/retrieve-metadata/SKILL.md` | The `retrieve-metadata` skill: fetch + cache dataset metadata into `retrieved_metadata/<short_name>/` |
| `skills/evaluate-dataset/SKILL.md` | The `evaluate-dataset` skill and evaluation workflow (run folder, skip/rerun, downloaded-first metadata; supports Batch / non-interactive mode) |
| `skills/fair4ai-scoring/SKILL.md` | The `fair4ai-scoring` skill wrapping the scoring script |
| `skills/batch-evaluate-datasets/SKILL.md` | The `batch-evaluate-datasets` coordinator skill: parallel per-dataset evals → hands off to `summarize-outputs` |
| `skills/summarize-outputs/SKILL.md` | The `summarize-outputs` skill: compile any results directory → scores CSV + figure + report (dedups reruns) |
| `scripts/build_response_scaffold.py` | Builds the 89-item evaluation scaffold JSON with verbatim checklist fields, plus a compact per-section rating guide (stdlib-only) |
| `scripts/merge_ratings.py` | Merges per-section ratings into the scaffold in place, with status validation and the "Never NA" guard (stdlib-only) |
| `scripts/compute_fair4ai_scores.py` | Deterministic 0–1 FAIR4AI scoring tool (stdlib-only) |
| `scripts/compile_fair4ai_results.py` | Compiles a folder of evaluation JSONs into a scores CSV + aggregates, including each evaluation's agent version (stdlib-only) |
| `scripts/fair4ai_version.py` | Reads the agent version and builds the `session.agent_provenance` stamp used by the scripts above (stdlib-only) |
| `scripts/make_fair4ai_figure.py` | Renders the 5×2 two-column (left = FAIR, right = AI-FAIR) score-distribution figure (needs numpy + matplotlib) |
| `scripts/requirements-viz.txt` | Optional deps (numpy, matplotlib) for the figure only |
| `example_inputs/` | Sample batch input lists (`.csv` and `.md`) for `batch-evaluate-datasets`, and example metadata folders |
| `VERSION.txt` | The agent version (semantic versioning), stamped into every evaluation |
| `CHANGELOG.md` | What changed in each agent version, and the versioning policy |
| `CHECKLIST.csv` | 89-item FAIR4AI-Bio checklist (9 sections; each item carries a `Requirement Definition` and a per-item `Scoring: NA` condition, and is mapped to EML, DataCite, Schema.org, Croissant, its FAIR4AI dimension(s), and its Structural/Scientific/Provenance/Governance AI FAIR criteria). The meets/partial/does-not-meet judgment is guided by `RATING_RUBRIC.md` §4. |
| `RATING_RUBRIC.md` | Authority for choosing each item's `meets / partial / does not meet / N/A` status |
| `CHECKLIST_OVERVIEW.md` | Narrative description of all 9 checklist sections |
| `QUICKSTART.md` | Step-by-step usage guide with example sessions |
| `example_outputs/` | Complete example evaluation reports (a NEON observational dataset + the TreeOfLife-200M image corpus) — newest also serves as the output template |
| `tests/` | Stdlib-only regression tests for the scripts, example outputs, and plugin layout (`python -m unittest discover -s tests`; see `tests/README.md`) |
| `LICENSE` | License for this repository |

---

## Checklist sections

1. **General Information** — bibliographic metadata, data dictionary, machine-readiness flag
2. **Data Structure** — file formats, dataset organization, variables, technical specs
3. **Source Data** — collection type, instrumentation/sensor metadata, sampling design
4. **Data Processing** — transformations, gap-filling, annotation provenance, train/val/test split definitions
5. **Data Quality** — completeness, consistency, integrity, timeliness
6. **Guidance & Recommendations** — biases, class imbalance, non-detections, prior AI/ML usage history
7. **Data Access** — delivery options, format openness, license (SPDX identifier), privacy controls
8. **Provenance** — citation (DOI, ORCIDs, checksums), processing platform, source-data chain for derived datasets
9. **Data Governance** — ethical / CARE governance (storage conditions, permission to collect, granting agent, implicated communities), per the CARE Data Governance specification (IEEE, 2025)

---

## Related

This agent was split out of the `fair4ai-eval-agent/` folder of the working group's [FAIR4AI-checklists](https://github.com/FAIR4AI-Bio/FAIR4AI-checklists) repository, which holds the FAIR4AI / AI-ready definitions and the checklist-development notes (`agent_and_checklist_review/`) cited in `RATING_RUBRIC.md`.

When you develop from a clone, run folders the skills create at the repository root (`fair4ai_run_*/`, `batch_run_*/`, `TEST_OUTPUT/`, a root-level `retrieved_metadata/` or `evaluate_progress.md`) are git-ignored, as is the machine-specific `.claude/settings.local.json`.
