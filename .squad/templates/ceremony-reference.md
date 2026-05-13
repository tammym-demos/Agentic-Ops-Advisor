# Ceremony Reference

On-demand reference for Squad ceremonies. Loaded when a ceremony triggers or the user requests one.

## Config Format

Each ceremony in `ceremonies.md` has these fields:

| Field | Values | Description |
|-------|--------|-------------|
| **Trigger** | `auto` / `manual` | Auto = checked before/after work batches. Manual = user requests. |
| **When** | `before` / `after` | Runs before or after the work batch. |
| **Condition** | free text | Describes when auto-trigger fires (e.g., "multi-agent task involving 2+ agents"). |
| **Facilitator** | `lead` / `{agent-name}` | Who runs the meeting. |
| **Participants** | `all-relevant` / `all-involved` / `{agent-list}` | Who attends. |
| **Time budget** | `focused` / `extended` | Focused = minimal, get decisions fast. Extended = thorough discussion. |
| **Enabled** | `✅ yes` / `❌ no` | Toggle without deleting the ceremony. |

## Facilitator Spawn Template

```
agent_type: "general-purpose"
model: "{resolved_model}"
mode: "sync"
description: "{emoji} {Facilitator}: Facilitating {CeremonyName}"
prompt: |
  You are {Facilitator}, facilitating a {CeremonyName} ceremony.
  TEAM ROOT: {team_root}
  **Requested by:** {current user name}

  CEREMONY CONFIG:
  {paste the ceremony block from ceremonies.md}

  PARTICIPANTS: {list of agent names and roles}
  TASK CONTEXT: {what work is about to happen or just happened}

  Run the agenda. For each item:
  1. State the question clearly
  2. Spawn relevant participants as sub-tasks to get their input
  3. Synthesize into decisions

  Output:
  - Decisions made (numbered)
  - Action items (assigned to specific agents)
  - Any risks flagged

  Write decisions to .squad/decisions/inbox/{facilitator}-{ceremony-slug}.md

  ⚠️ RESPONSE ORDER: After ALL tool calls, write a plain text summary as FINAL output.
```

## Execution Rules

1. **Before ceremonies** (`when: "before"`): Run the ceremony sync, include its summary in the work batch spawn prompts.
2. **After ceremonies** (`when: "after"`): Run after collecting batch results. Spawn Scribe afterward.
3. **Manual ceremonies**: Only run when the user says "run a retro", "design meeting", etc.
4. **Cooldown**: After running a ceremony, skip auto-trigger checks for the immediately following step.
5. **Disabled ceremonies**: Skip entirely — don't mention them.
