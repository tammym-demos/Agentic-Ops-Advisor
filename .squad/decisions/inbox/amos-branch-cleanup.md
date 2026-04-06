# Decision: Branch Cleanup — Merge Strategy for Stale copilot/* Branches

**Date:** 2026-04-06
**Author:** Amos (DevOps)
**Status:** Executed

## Context

The repository had 19 `copilot/*` branches from original @copilot coding agent PRs. Since those PRs, extensive work was done directly on main (v2 SDK migration, health endpoint, Docker optimization, deploy.yml rewrite, test fixes). The old branches contained stale versions of core files.

## Decision

- **Merged remote branches (10 previously merged):** Deleted from remote. 7 were already gone; 3 remaining deleted.
- **Unmerged branches (7 local):** Merged into main using `--ours` conflict resolution to preserve main's up-to-date code. This effectively closes the branch history without losing any git lineage.
- **Remote-only unmerged branches (2):** `add-comprehensive-readme-for-operators` and `create-landing-page-brochure` were already deleted from remote before this task. Their content would need to be re-contributed if still wanted.

## Rationale

All conflicts involved files that had been rewritten on main for the v2 SDK migration (agent.py, config.py, tools/, tests/). Keeping main's version was the correct choice — the branch versions were pre-migration and would break the agent.

## Impact

- 348 tests pass post-merge
- Repository reduced from 20 branches to 2 (main + one unrelated)
- Git history preserves all branch lineage via merge commits
