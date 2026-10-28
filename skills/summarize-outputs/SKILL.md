---
name: summarize-outputs
description: Summarize a directory of FAIR4AI evaluation JSONs into a compiled scores CSV, a summary figure, and a narrative Markdown report. By default ignores superseded (older) re-runs of a dataset, keeping only the newest per dataset. Invoke as /fair4ai-evaluator:summarize-outputs (Claude Code), or whenever asked to summarize/compile/report across a folder of FAIR4AI evaluations. Also invoked by the batch-evaluate-datasets coordinator after it finishes evaluating.
---

You summarize a directory of FAIR4AI-Bio evaluation JSONs. You do **not** evaluate
datasets — you compile the existing `FAIR4AI_eval_*.json` files into a scores CSV, a
summary figure, and a narrative report. By default you keep only the **newest run of
each dataset** (dedup), so re-run outputs don't double-count; the user can override
this to include every run.

The scoring, compilation, and figure are done by scripts; you author the narrative
report and report to the user.

## Plugin files

This skill ships in the **`fair4ai-evaluator`** plugin. `<PLUGIN_ROOT>` below means the plugin's
root directory, which is `${CLAUDE_PLUGIN_ROOT}`. If that is not an absolute path (your harness
left the placeholder unexpanded), `<PLUGIN_ROOT>` is the directory two levels above this
`SKILL.md` — the one holding `plugin.json`, `CHECKLIST.csv`, and `scripts/`. Resolve it to an
absolute path once, quote it in shell commands, and treat it as **read-only**: never edit or
add files there. Outputs go to the user's working directory or to the paths you are given.

## Step 1: Gather parameters

Present this prompt and wait (skip when invoked by the batch coordinator, which
supplies these):

---
**FAIR4AI Summarize Outputs — Parameters**

1. **Results directory** *(required)* — a folder containing `FAIR4AI_eval_*.json`
   files (a batch run folder's `evaluation_results/`, or any directory of evaluations).
2. **Output directory** *(optional)* — where the CSV / figure / report are written.
   Default: the results directory (or its parent run folder).
3. **Dedup mode** *(optional)* — `latest` (default: one row per dataset, newest run) or
   `all` (every run, one row per file).
4. **Source CSV** *(optional)* — a normalized `email,name,dataset_short_name,url,notes`
   list. If omitted, datasets and their url/title/email are derived from the JSONs.
5. **Confidence map** *(optional)* — `{ "<short_name>": "high|medium|low" }` JSON.
6. **Label** *(optional)* — used in output filenames. Default: current
   `date +%Y-%m-%d_%H%M%S`.
7. **Report title / subtitle** *(optional)* — defaults derived from the dataset count.
8. **Model label** *(optional)* — the model that produced the evaluations (for the
   figure footnote and report header).
---

Confirm resolved parameters (substituting defaults) before proceeding.

## Step 2: Compile the scores CSV

Run the compiler. `--source-csv` and `--confidence-map` are optional; `--dedup`
defaults to `latest`:

```bash
python "<PLUGIN_ROOT>/scripts/compile_fair4ai_results.py" \
  --results-dir "<results dir>" \
  --dedup <latest|all> \
  --out-csv "<output dir>/fair4ai_scores_summary_<LABEL>.csv" \
  [--source-csv "<source csv>"] \
  [--confidence-map "<confidence map>"]
```

Invoke every Python call with the `python` command exactly as written. If `python` is not
found, use `py -3` on Windows (never `python3` there — it may resolve to the Microsoft Store
redirector and open the install manager) and `python3` on Linux/macOS. The scripts are
stdlib-only, so no `pip`/install step is ever needed.

Capture the printed **`AGG:{...}`** line — it carries `n_total`, `dedup`, `missing`,
`superseded` (older runs ignored under `latest`), `fair_means` (F/A/I/R),
`overall_fair_mean`, `ai_fair_means` (ml_ready/ai_ready_for_task/traceable/
care_compliance), `overall_ai_fair_mean`, `by_confidence` groupings, and the version
fields `by_agent_version` (agent version → datasets; `unversioned` for evaluations that
predate versioning), `checklist_sha256s`, and `mixed_versions` — you cite these in the
report. The CSV also carries per-row `agent_version`, `scored_with_version`, and
`checklist_sha256` columns. Note any `Superseded (…)` / `WARNING:` lines on stderr.

## Step 3: Build the summary figure (optional / graceful)

```bash
python "<PLUGIN_ROOT>/scripts/make_fair4ai_figure.py" \
  --in-csv "<output dir>/fair4ai_scores_summary_<LABEL>.csv" \
  --out-base "<output dir>/fair4ai_score_distributions_<LABEL>" \
  --model "<model label>" --date <LABEL>
```

This needs `numpy` + `matplotlib`. If it exits non-zero with an import error, report
*"figure skipped — install `<PLUGIN_ROOT>/scripts/requirements-viz.txt`"* and **continue** (the CSV
and report are still produced). Pass `--title` / `--subtitle` if custom text was given.

## Step 4: Author the narrative summary report

Write **`<output dir>/FAIR4AI_summary_report_<LABEL>.md`**, mirroring the structure and
tone of prior summary reports, if any are available. Include:

- **Header** — label/date, checklist (89 items), **agent version(s)** (from AGG
  `by_agent_version`), evaluation model (the model label), summarizer model (this
  session), scoring method (one line), and a **coverage** line:
  n datasets summarized; note any `missing` datasets and, when `dedup=latest`, that
  older re-runs were **superseded** (list them from the AGG `superseded` field).
- **Scores at a glance** — two tables (or one wide table), **sorted by Overall AI-FAIR
  desc**: a **Traditional FAIR** table (findable / accessible / interoperable / reusable
  / Overall FAIR) and an **AI-FAIR** table (ml_ready / ai_ready_for_task / traceable /
  care_compliance / Overall AI-FAIR), each with a final **Mean (n=…)** row (from the AGG
  `fair_means`/`overall_fair_mean` and `ai_fair_means`/`overall_ai_fair_mean`).
- **Status breakdown** — per-dataset meets / partial / does not meet / N/A counts (CSV).
- **Cross-dataset patterns** — strongest and weakest dimensions in each assessment, and
  the size of the **Overall FAIR vs Overall AI-FAIR gap**. Anchor on the thesis: *FAIR ≠
  AI-ready* — datasets strong on Traditional FAIR still lag on AI-FAIR (especially CARE
  compliance and the scientific facet).
- **Per-dataset summaries** — a short paragraph + top gaps/recommendations per dataset.
- **Caveats** — note that ratings were produced by the evaluation model, that this is a
  **metadata-only** evaluation, flag low-confidence datasets, and (when `dedup=all`) note
  that multiple runs of the same dataset are included. When AGG `mixed_versions` is
  true, say which datasets came from which agent version / checklist and that their
  scores are not strictly comparable (a MAJOR version change means the checklist or
  scoring rules changed).
- **Artifacts** — a table linking the scores CSV, the figure (if produced), each
  evaluation JSON, and the source/confidence inputs if used.

## Step 5: Report to the user

- The **output directory** and a listing of what was written.
- **n datasets summarized** (and n superseded/ignored, n missing).
- The **agent version(s)** the evaluations came from, flagging mixed versions.
- **Mean Overall FAIR** and **Mean Overall AI-FAIR** (and per-dimension/per-category
  means), noting they are script-computed (reproducible), and the typical FAIR-vs-AI-FAIR
  gap.
- Paths to the scores CSV, figure, and summary report.
- The top 3–5 cross-dataset gaps.
