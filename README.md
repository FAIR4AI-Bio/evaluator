# FAIR4AI Dataset Evaluation Agent (`evaluator`)

Repository for the FAIR4AI evaluation agentic workflow, maintained by the [FAIR4AI-Bio](https://github.com/FAIR4AI-Bio) working group.

An AI agent that evaluates biodiversity, ecology, and environmental science datasets for AI-readiness using the **FAIR4AI-Bio checklist**. The agent reads a dataset's landing page or local metadata files, rates each of the 89 checklist items as *meets / partial / does not meet / N/A* (judged against each item's `Requirement Definition` and the section-level guidance in `RATING_RUBRIC.md`), and produces a structured JSON report with **two reproducible assessments** — **Traditional FAIR** (Findable, Accessible, Interoperable, Reusable + an overall) and **AI-FAIR** (ML-ready, AI-ready for task, Traceable, CARE compliance + an overall) — each score in **0–1, where 1 is "most FAIR4AI"**, computed by the `fair4ai-scoring` skill.

The core thesis: **FAIR compliance is necessary but not sufficient for AI-ready data.** Reporting FAIR and AI-FAIR side by side makes that gap measurable.

See `example_outputs/` for complete evaluation reports for two example datasets — a NEON observational dataset (ground beetles) and the TreeOfLife-200M image corpus (Hugging Face).

---

## Requirements

- A dataset source: URL to a landing page, or a local directory containing metadata files (JSON-LD, EML, DataCite XML, README, etc.)
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed

---

## Setup

Clone this repository and open Claude Code with the repository root as the working directory:

```bash
git clone https://github.com/FAIR4AI-Bio/evaluator.git
cd evaluator
claude
```

No additional setup steps are required. The `/evaluate-dataset` skill is defined in `.claude/skills/evaluate-dataset/SKILL.md` and is tracked in this repository.

In the Claude Code chat, type:

```
/evaluate-dataset
```

The agent will prompt you for the dataset source and other parameters. Press Enter to accept defaults for optional parameters.

---

## Batch evaluation

To evaluate **many datasets at once**, use the `/batch-evaluate-datasets` skill:

```
/batch-evaluate-datasets
```

It reads a **flexible dataset list** — a `.txt`, `.csv`, or `.md` file — parses out each dataset and its URL regardless of layout, and normalizes it into a standard CSV (`email,name,dataset_short_name,url,notes`). It then coordinates **one sub-agent per dataset in parallel** (launched in waves of 5 by default), each running the `/evaluate-dataset` workflow non-interactively, and finally **hands off to the `summarize-outputs` skill** for the scores CSV, figure, and report. The default sub-agent model is **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`); the skill asks whether to use it or a different model.

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

The run is **resumable** — re-invoking the skill on an existing run folder reads `batch_evaluate_progress.md` and re-runs only the datasets that are still pending or failed. Evaluation filenames carry a timestamp to the second, so re-runs of a dataset never collide; `summarize-outputs` keeps only the newest run of each dataset by default. The summary **figure** needs `numpy` + `matplotlib` (`pip install -r scripts/requirements-viz.txt`); if they're absent the figure is skipped and the CSV + report are still produced (scoring and compilation are stdlib-only).

---

## How the agent files work

Claude Code reads these files automatically when you start a session in this directory:

- **`CLAUDE.md`** — project context loaded into every session: what the agent does, how the checklist is structured, the output JSON schema, and expected score patterns.
- **`.claude/skills/retrieve-metadata/SKILL.md`** — the `/retrieve-metadata` skill: fetches a dataset's metadata (URL or local path) and, by default, saves it under `retrieved_metadata/<short_name>/` so it can be reused without re-fetching. Called on its own or internally by `evaluate-dataset`.
- **`.claude/skills/evaluate-dataset/SKILL.md`** — the `/evaluate-dataset` skill. Establishes a run folder, skips datasets already evaluated (unless a re-run is requested), looks for already-downloaded metadata before calling `retrieve-metadata`, rates each item, builds the output JSON, and computes scores.
- **`RATING_RUBRIC.md`** — the authority for how each item's `meets / partial / does not meet / N/A` status is chosen (including the N/A rule).
- **`.claude/skills/fair4ai-scoring/SKILL.md`** + **`scripts/compute_fair4ai_scores.py`** — the skill and deterministic tool that compute `summary.fair4ai_scores` (0–1) from the per-item statuses: Traditional FAIR from each item's `FAIR category`, and AI-FAIR from each item's `AI FAIR Criteria` value.
- **`.claude/skills/batch-evaluate-datasets/SKILL.md`** — the `/batch-evaluate-datasets` **coordinator** skill: reads a dataset list and orchestrates parallel per-dataset sub-agents (reusing `evaluate-dataset` in Batch / non-interactive mode), then hands off to `summarize-outputs` for the CSV, figure, and report.
- **`.claude/skills/summarize-outputs/SKILL.md`** — the `/summarize-outputs` skill: compiles any directory of evaluation JSONs into a scores CSV, summary figure, and narrative report (via `scripts/compile_fair4ai_results.py` and `scripts/make_fair4ai_figure.py`); keeps only the newest run of each dataset by default.

All five capabilities live under `.claude/skills/` (one skill per directory, each with a `SKILL.md`). To modify agent behavior, edit these files directly. Changes are tracked in git and shared across the team.

---

## Versioning

The agent is versioned with [semantic versioning](https://semver.org/). The current version is in the
repo-root **`VERSION`** file (currently **0.1.0**; print it with `python scripts/fair4ai_version.py`),
each release is tagged `v<version>` in git, and **`CHANGELOG.md`** lists what changed. A **MAJOR**
bump means the checklist items or scoring rules changed, so scores are no longer comparable with
earlier versions; **MINOR** covers new features or rubric/skill changes that may shift ratings;
**PATCH** covers fixes and documentation.

Every evaluation records which version produced it in `session.agent_provenance`:

```json
"agent_provenance": {
  "agent_version": "0.1.0",
  "git_commit": "<full commit of this repo>",
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
| `CLAUDE.md` | Project context auto-loaded by Claude Code each session |
| `.claude/skills/retrieve-metadata/SKILL.md` | The `/retrieve-metadata` skill: fetch + cache dataset metadata into `retrieved_metadata/<short_name>/` |
| `.claude/skills/evaluate-dataset/SKILL.md` | The `/evaluate-dataset` skill and evaluation workflow (run folder, skip/rerun, downloaded-first metadata; supports Batch / non-interactive mode) |
| `.claude/skills/fair4ai-scoring/SKILL.md` | The `/fair4ai-scoring` skill wrapping the scoring script |
| `.claude/skills/batch-evaluate-datasets/SKILL.md` | The `/batch-evaluate-datasets` coordinator skill: parallel per-dataset evals → hands off to `summarize-outputs` |
| `.claude/skills/summarize-outputs/SKILL.md` | The `/summarize-outputs` skill: compile any results directory → scores CSV + figure + report (dedups reruns) |
| `scripts/build_response_scaffold.py` | Builds the 89-item evaluation scaffold JSON with verbatim checklist fields, plus a compact per-section rating guide (stdlib-only) |
| `scripts/merge_ratings.py` | Merges per-section ratings into the scaffold in place, with status validation and the "Never NA" guard (stdlib-only) |
| `scripts/compute_fair4ai_scores.py` | Deterministic 0–1 FAIR4AI scoring tool (stdlib-only) |
| `scripts/compile_fair4ai_results.py` | Compiles a folder of evaluation JSONs into a scores CSV + aggregates, including each evaluation's agent version (stdlib-only) |
| `scripts/fair4ai_version.py` | Reads the agent version and builds the `session.agent_provenance` stamp used by the scripts above (stdlib-only) |
| `scripts/make_fair4ai_figure.py` | Renders the 5×2 two-column (left = FAIR, right = AI-FAIR) score-distribution figure (needs numpy + matplotlib) |
| `scripts/requirements-viz.txt` | Optional deps (numpy, matplotlib) for the figure only |
| `example_inputs/` | Sample batch input lists (`.csv` and `.md`) for `/batch-evaluate-datasets` |
| `VERSION` | The agent version (semantic versioning), stamped into every evaluation |
| `CHANGELOG.md` | What changed in each agent version, and the versioning policy |
| `CHECKLIST.csv` | 89-item FAIR4AI-Bio checklist (9 sections; each item carries a `Requirement Definition` and a per-item `Scoring: NA` condition, and is mapped to EML, DataCite, Schema.org, Croissant, its FAIR4AI dimension(s), and its Structural/Scientific/Provenance/Governance AI FAIR criteria). The meets/partial/does-not-meet judgment is guided by `RATING_RUBRIC.md` §4. |
| `RATING_RUBRIC.md` | Authority for choosing each item's `meets / partial / does not meet / N/A` status |
| `CHECKLIST_OVERVIEW.md` | Narrative description of all 9 checklist sections |
| `QUICKSTART.md` | Step-by-step usage guide with example sessions |
| `example_outputs/` | Complete example evaluation reports (a NEON observational dataset + the TreeOfLife-200M image corpus) — newest also serves as the output template |
| `tests/` | Stdlib-only regression tests for the scripts and example outputs (`python -m unittest discover -s tests`; see `tests/README.md`) |
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

Run folders the skills create at the repository root (`fair4ai_run_*/`, `batch_run_*/`, `TEST_OUTPUT/`, a root-level `retrieved_metadata/` or `evaluate_progress.md`) are git-ignored, as is the machine-specific `.claude/settings.local.json`.
