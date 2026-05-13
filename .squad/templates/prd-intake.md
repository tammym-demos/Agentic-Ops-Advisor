# PRD Intake

On-demand reference for PRD Mode. Loaded when the user provides a PRD or spec document.

## Triggers

| User says | Action |
|-----------|--------|
| "here's the PRD" / "work from this spec" | Expect file path or pasted content |
| "read the PRD at {path}" | Read the file |
| "the PRD changed" / "updated the spec" | Re-read and diff against previous decomposition |
| (pastes requirements text) | Treat as inline PRD |

## Intake Flow

1. **Detect source:** File path, pasted content, or URL.
2. **Store PRD reference** in `team.md` under `## PRD`:
   ```
   ## PRD
   - **Source:** {path or "inline"}
   - **Ingested:** {timestamp}
   - **Version:** {hash or "v1"}
   ```
3. **Spawn Lead** (sync, premium model bump) to decompose:

```
agent_type: "general-purpose"
model: "{premium_model}"
mode: "sync"
description: "🏗️ {Lead}: Decomposing PRD into work items"
prompt: |
  You are {Lead}, the Lead on this project.
  TEAM ROOT: {team_root}
  **Requested by:** {current user name}

  Read the PRD below and decompose it into work items.

  PRD CONTENT:
  {full PRD text}

  For each work item:
  - **ID:** WI-{number}
  - **Title:** clear, actionable title
  - **Agent:** who should do it (from team roster)
  - **Dependencies:** which WIs must complete first
  - **Priority:** P0 (critical path) / P1 (important) / P2 (nice to have)
  - **Size:** S (hours) / M (day) / L (multi-day)
  - **Acceptance criteria:** measurable, testable outcomes

  Output a table of work items sorted by priority and dependency order.
  Flag any ambiguities or missing requirements.

  Write decomposition to .squad/plans/prd-decomposition.md

  ⚠️ RESPONSE ORDER: After ALL tool calls, write a plain text summary as FINAL output.
```

4. **Present work items** as a table for user approval.
5. **Route approved items** respecting dependency order — spawn agents for items with no pending dependencies.

## Mid-Project Updates

When "the PRD changed":
1. Re-read the PRD
2. Spawn Lead to diff against `.squad/plans/prd-decomposition.md`
3. Present: new items, changed items, removed items
4. Get user approval before routing changes
