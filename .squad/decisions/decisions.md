# Decisions

## Branch Cleanup — Merge Strategy for Stale copilot/* Branches

**Date:** 2026-04-06  
**Author:** Amos (DevOps)  
**Status:** Executed

### Context
Repository had 19 `copilot/*` branches from original @copilot coding agent PRs. Extensive work done directly on main (v2 SDK migration, health endpoint, Docker optimization, deploy.yml rewrite, test fixes). Old branches contained stale versions of core files.

### Decision
- **Merged remote branches (10 previously merged):** Deleted from remote. 7 already gone; 3 remaining deleted.
- **Unmerged branches (7 local):** Merged into main using `--ours` conflict resolution to preserve main's up-to-date code. Closes branch history without losing git lineage.
- **Remote-only unmerged branches (2):** `add-comprehensive-readme-for-operators` and `create-landing-page-brochure` already deleted from remote. Content would need re-contribution if still wanted.

### Rationale
All conflicts involved files rewritten on main for v2 SDK migration (agent.py, config.py, tools/, tests/). Keeping main's version was correct — branch versions pre-migration would break the agent.

### Impact
- 348 tests pass post-merge
- Repository reduced from 20 branches to 2 (main + one unrelated)
- Git history preserves all branch lineage via merge commits
