# Copilot Coding Agent Member

On-demand reference for managing @copilot as a Squad team member.

## Adding @copilot

1. Add to `team.md` roster:
   ```
   | @copilot | Coding Agent | [instructions](../../.github/copilot-instructions.md) | 🤖 Cloud |
   ```
2. Add capability profile table to `team.md` (see below)
3. Add routing entry to `routing.md`:
   ```
   | Cloud code fixes, single-file changes, issue-driven code work | @copilot | Coding Agent — async via issue assignment, creates PRs |
   ```
4. Do NOT create charter.md — @copilot uses `.github/copilot-instructions.md`
5. Ask about auto-assign: "Should @copilot auto-pick-up `squad:copilot` issues?"
   - If yes: add `<!-- copilot-auto-assign: true -->` to team.md
   - If no: add `<!-- copilot-auto-assign: false -->`

## Comparison: @copilot vs AI Agent vs Human

| Aspect | AI Agent | @copilot | Human |
|--------|----------|----------|-------|
| Badge | Role emoji | 🤖 Coding Agent | 👤 Human |
| Name | Cast name | Always "@copilot" | Real name |
| Spawnable | ✅ via `task` tool | ❌ via issue assignment | ❌ Not spawnable |
| Work style | Sync/async in session | Async — creates branches + PRs | Present and wait |
| Instructions | charter.md | copilot-instructions.md | None |

## Capability Profile

The Lead evaluates issues against this profile during triage:

| Category | Fit | Notes |
|----------|-----|-------|
| Single-file code fixes | 🟢 | Ideal — scoped, testable |
| Multi-file refactors | 🟢 | Good with clear instructions |
| New feature from issue | 🟡 | Works if well-specified |
| Config/IaC changes | 🟡 | Can edit, can't deploy |
| External service operations | 🔴 | No credentials in cloud runner |
| Database operations | 🔴 | No DB access in cloud runner |
| Test execution | 🟡 | Can run if setup-steps configured |

## Auto-Assign Behavior

When `copilot-auto-assign: true`:
- Issues labeled `squad:copilot` are automatically assigned to @copilot
- The `squad-issue-assign.yml` workflow handles assignment
- @copilot creates a `copilot/*` branch and opens a draft PR

When `copilot-auto-assign: false`:
- Issues labeled `squad:copilot` wait for manual assignment
- The Lead or coordinator decides when to assign

## Lead Triage for @copilot

During triage, the Lead checks:
1. Does the issue match a 🟢 capability? → Assign to @copilot
2. Does it match a 🟡 capability? → Assign only if well-specified
3. Does it match a 🔴 capability? → Route to an AI agent or human instead
