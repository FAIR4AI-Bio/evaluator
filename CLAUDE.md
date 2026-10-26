# CLAUDE.md

@AGENTS.md

## Claude Code notes

- This file and `AGENTS.md` are context for **developing** the `fair4ai-evaluator` plugin. Claude
  Code does not load a plugin's `CLAUDE.md` for people who install it.
- Load the working tree as the plugin: `claude --plugin-dir .`. The skills are then available as
  `/fair4ai-evaluator:<skill>`. Run `/reload-plugins` after editing a skill.
- Check the manifests with `claude plugin validate .`.
- Test installing through the marketplace: `/plugin marketplace add ./` and then
  `/plugin install fair4ai-evaluator@fair4ai-bio`.
