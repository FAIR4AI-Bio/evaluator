#!/usr/bin/env python
"""Agent version + provenance stamp shared by the FAIR4AI helper scripts.

Every evaluation JSON records which version of the agent produced it, in
`session.agent_provenance`, so scores from different agent/checklist versions are
never silently compared:

    "agent_provenance": {
      "agent_version": "0.1.0",          # the plugin-root VERSION.txt file
      "git_commit": "2660ffd...",        # full commit of the agent repo (null if not a git checkout)
      "git_dirty": false,                # true if tracked files had uncommitted changes
      "checklist_file": "CHECKLIST.csv", # basename of the checklist actually used
      "checklist_sha256": "...",         # fingerprint of that checklist (line endings normalized)
      "scored_with_version": "0.1.0",    # agent version of the scorer that wrote summary.fair4ai_scores
      "scored_with_commit": "2660ffd..."
    }

The first five fields are stamped by build_response_scaffold.py (it knows the
checklist in use); the `scored_with_*` pair is stamped by compute_fair4ai_scores.py
each time it writes scores. These fields are script-owned: merge_ratings.py carries
them over when the agent replaces the session block, so a sub-agent can neither omit
nor mistype them.

Versioning policy (semantic versioning, see CHANGELOG.md): bump MAJOR when the
checklist items or the scoring rules change (scores are no longer comparable),
MINOR for new features or rubric/skill changes that may shift ratings, PATCH for
fixes and documentation.

Stdlib only. Usage:
    python scripts/fair4ai_version.py                      # print the agent version
    python scripts/fair4ai_version.py --json [--checklist /abs/CHECKLIST.csv]
"""
import argparse
import hashlib
import json
import os
import subprocess

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(AGENT_DIR, "VERSION.txt")
MANIFEST_FILE = os.path.join(AGENT_DIR, "plugin.json")
PROVENANCE_KEY = "agent_provenance"
SCAFFOLD_FIELDS = ["agent_version", "git_commit", "git_dirty",
                   "checklist_file", "checklist_sha256"]
SCORER_FIELDS = ["scored_with_version", "scored_with_commit"]


def get_version():
    """The agent version from the plugin-root VERSION.txt file, or 'unknown'.

    Falls back to the `version` in the root plugin.json when VERSION.txt is missing or
    empty (e.g. a harness that packaged the plugin without it).
    """
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            text = f.read().strip()
        if text:
            return text
    except OSError:
        pass
    try:
        with open(MANIFEST_FILE, encoding="utf-8") as f:
            return str(json.load(f).get("version") or "").strip() or "unknown"
    except (OSError, ValueError, AttributeError):
        return "unknown"


def _git(*args):
    try:
        out = subprocess.run(["git", "-C", AGENT_DIR, *args], capture_output=True,
                             text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def get_git_commit():
    """Full commit hash of the agent repo, or None outside a git checkout."""
    return _git("rev-parse", "HEAD") or None


def get_git_dirty():
    """True if tracked files have uncommitted changes; None if git is unavailable."""
    status = _git("status", "--porcelain", "--untracked-files=no")
    return None if status is None else bool(status)


def checklist_sha256(path):
    """SHA-256 of the checklist file, or None if it can't be read.

    Line endings are normalized to LF first, so the same checklist gets the same
    fingerprint on a Windows (CRLF) and a Linux/macOS (LF) checkout.
    """
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest()
    except OSError:
        return None


def scaffold_provenance(checklist_path=None):
    """The provenance block written when an evaluation scaffold is built."""
    return {
        "agent_version": get_version(),
        "git_commit": get_git_commit(),
        "git_dirty": get_git_dirty(),
        "checklist_file": os.path.basename(checklist_path) if checklist_path else None,
        "checklist_sha256": checklist_sha256(checklist_path) if checklist_path else None,
    }


def stamp_scored_with(doc):
    """Record the scorer's version in session.agent_provenance (in place).

    Evaluations that predate versioning have no provenance block; one is created with
    the scaffold fields set to null (unknown) rather than guessed. Returns True when
    the scaffold fields were missing.
    """
    session = doc.get("session")
    if not isinstance(session, dict):
        session = doc["session"] = {}
    prov = session.get(PROVENANCE_KEY)
    missing = not isinstance(prov, dict) or not prov.get("agent_version")
    if not isinstance(prov, dict):
        prov = session[PROVENANCE_KEY] = {k: None for k in SCAFFOLD_FIELDS}
    prov["scored_with_version"] = get_version()
    prov["scored_with_commit"] = get_git_commit()
    return missing


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print the FAIR4AI evaluator agent version.")
    ap.add_argument("--json", action="store_true", help="print the full provenance block as JSON")
    ap.add_argument("--checklist", help="checklist to fingerprint (with --json)")
    args = ap.parse_args(argv)
    if args.json:
        print(json.dumps(scaffold_provenance(args.checklist), indent=2))
    else:
        print(get_version())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
