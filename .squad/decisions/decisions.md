# Decisions

## Infrastructure Alignment — CognitiveServices-based Bicep Rewrite

**Date:** 2025-06-XX  
**Author:** Amos (DevOps)  
**Status:** Completed; under review  
**Reviewer:** Holden (Lead)

### Context
Live infrastructure uses CognitiveServices AIServices Hub with native GPT-4.1 deployment. Original Bicep templates used MachineLearningServices workspace model, creating a critical mismatch.

### Decision
Rewrote Bicep templates (`aifoundry.bicep`, `openai.bicep`, `main.bicep`) to match live architecture. Converts Hub from ML workspace to CognitiveServices AIServices, deploys GPT-4.1 model natively on Hub as child resource, removes standalone OpenAI module.

### Impact
- **Architecture now matches reality** — safe to redeploy
- **Backward compatible outputs** — no CI/CD changes needed
- **Future extensibility** — can add/modify model deployments via IaC

### Review Status
**Holden's verdict:** ✅ APPROVE WITH CRITICAL FIX (See separate Architecture Review entry below)

---

## Bicep Rewrite — Architecture Review (Critical Issue)

**Date:** 2026-04-07  
**Reviewer:** Holden (Lead)  
**Context:** Amos's Bicep rewrite (Option 1) — CognitiveServices Hub with native model deployment

### Verdict: ⚠️ APPROVE WITH CRITICAL FIX REQUIRED

**Critical blocking issue:** Child resource `location` property on Project will cause ARM deployment failure. Bicep line 144 must remove `location: location` from `aiProject` resource. Azure does not allow child resources to declare `location` — they inherit from parent.

**Secondary (non-blocking):**
- Remove `Microsoft.MachineLearningServices` from deploy.sh provider list (cleanup)
- Optimize `dependsOn` chain (optional performance improvement)

**Fix complexity:** 1-line deletion. Straightforward.

**Recommendation:** Fix blocking issue, merge, deploy to sandbox to validate.

---

## User Directive — Option 1 for Bicep Alignment

**Date:** 2026-04-07T21:00:00Z  
**By:** Tammy (via Copilot)  
**Decision:** Choose Option 1 (full IaC rewrite) over quick-gate workaround  
**Rationale:** User request for complete infrastructure alignment

---

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
