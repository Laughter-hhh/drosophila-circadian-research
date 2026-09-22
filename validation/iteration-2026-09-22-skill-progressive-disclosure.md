# Iteration report: progressive disclosure for skill routing

Date: 2026-09-22

## Issue identified

The auto-loaded `SKILL.md` contained 43 detailed workflow routes and measured 13,379 PowerShell characters across 119 lines. This loaded ephys, mixed-model, GEO, stock-audit, and specialized validation instructions even for unrelated Drosophila tasks. The skill's supported resources were already mostly separated into references, so the entrypoint repeated much of that routing detail.

## Change

- Kept the user-facing scope, core scientific model, task kickoff, research gates, evidence discipline, candidate/experiment defaults, output guidance, and common work routes in `SKILL.md`.
- Moved specialized script-level routes into `references/workflow-routing.md`, grouped by literature/candidates, experiments/genetics, GEO/public data, and raw-data/mixed-model work.
- Added an instruction to load only the matching routing section when a specialized workflow is actually needed.
- Added `tests/test_skill_routing.py` to check that the entrypoint stays below 10,000 characters and that all routed references/scripts/assets exist.

## Validation

- Main entrypoint decreased from **13,379 to 4,917 characters** (63.2% shorter); the on-demand routing index is 7,348 characters.
- Focused routing tests: **2 passed**.
- Full repository suite: **337 passed**.
- `git diff --check`: passed.
- `skill-creator/scripts/quick_validate.py` was attempted on the current repository version but could not start because the bundled Python lacks `PyYAML` (`ModuleNotFoundError: yaml`). The existing name/description frontmatter was unchanged; the new routing-resource test is a separate check and is not a substitute for the YAML validator.

## Scope limits

This change reduces default context and keeps the detailed routes available on demand; it does not alter analysis algorithms or scientific acceptance criteria. A fresh real-data forward task is running separately and has not yet been used to claim scientific workflow validation for this iteration.
