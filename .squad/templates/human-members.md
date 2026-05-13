# Human Team Members

On-demand reference for managing human members on the Squad roster.

## Triggers

| User says | Action |
|-----------|--------|
| "add {name} as {role}" | Add human member to roster |
| "{name}, what do you think?" | Route work to human, pause for relay |
| "remove {name}" | Archive human member |
| "{name} says..." | Relay human input to relevant agents |

## Comparison: Human vs AI Members

| Aspect | AI Agent | Human Member |
|--------|----------|-------------|
| Badge | Role emoji | 👤 Human |
| Name | Cast name (from universe) | Real name (no casting) |
| Charter | `.squad/agents/{name}/charter.md` | None |
| History | `.squad/agents/{name}/history.md` | None |
| Spawnable | ✅ via `task` tool | ❌ Not spawnable |
| Routing | Automatic via `routing.md` | Present work, wait for user relay |
| Reviewer lockout | Applies normally | Applies normally |

## Adding a Human Member

1. Add to `team.md` roster:
   ```
   | {Name} | {Role} | — | 👤 Human |
   ```
2. Add routing entry to `routing.md`:
   ```
   | {keywords} | {Name} | Human — {Role}, present work and wait for input |
   ```
3. Do NOT create charter.md or history.md — humans don't need them.
4. Say: "✅ {Name} joined the team as {Role} (human)."

## Routing to Humans

When work routes to a human:
1. Present the work clearly (what's needed, context, options if any)
2. Wait for the user to relay the human's input
3. Non-dependent work continues immediately — human blocks don't serialize the pipeline
4. Stale reminder after >1 turn without response: "📌 Still waiting on {Name} for {thing}."

## Removing a Human Member

1. Remove from `team.md` roster
2. Remove routing entries from `routing.md`
3. Say: "✅ {Name} removed from the team."
