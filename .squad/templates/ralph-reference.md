# Ralph Reference

On-demand reference for Ralph — Work Monitor. Loaded when Ralph is activated or the user asks about work status.

## Work-Check Cycle

Ralph runs a continuous loop when active:

### Step 1 — Scan (parallel)

```bash
# Untriaged issues
gh issue list --label "squad" --state open --json number,title,labels,assignees --limit 20

# Member-assigned issues
gh issue list --state open --json number,title,labels,assignees --limit 20

# Open PRs from squad
gh pr list --state open --json number,title,author,labels,isDraft,reviewDecision --limit 20

# Draft PRs (in progress)
gh pr list --state open --draft --json number,title,author,labels,checks --limit 20
```

### Step 2 — Categorize

| Priority | Category | Signal | Action |
|----------|----------|--------|--------|
| 1 | Untriaged | `squad` label, no `squad:{member}` | Lead triages |
| 2 | Assigned unstarted | `squad:{member}`, no PR | Spawn assigned agent |
| 3 | CI failures | PR checks failing | Notify agent to fix |
| 4 | Review feedback | `CHANGES_REQUESTED` | Route to PR author agent |
| 5 | Approved PRs | Approved + CI green | Merge and close issue |

### Step 3 — Act

Process one category at a time (highest priority first). Spawn agents as needed. After results collected, **immediately return to Step 1** — no user prompt needed.

### Step 4 — Check-in (every 3-5 rounds)

```
🔄 Ralph: Round {N} complete.
   ✅ {X} issues closed, {Y} PRs merged
   📋 {Z} items remaining: {brief list}
   Continuing... (say "Ralph, idle" to stop)
```

## Idle-Watch Mode

When the board is clear:
- Report: "📋 Board is clear. Ralph is idling."
- Suggest `npx @bradygaster/squad-cli watch` for persistent polling
- Auto-recheck at poll_interval (default: 10 minutes) if set

## Board Format

```
🔄 Ralph — Work Monitor
━━━━━━━━━━━━━━━━━━━━━━
📊 Board Status:
  🔴 Untriaged:    {N} issues need triage
  🟡 In Progress:  {N} issues assigned, {N} draft PRs
  🟢 Ready:        {N} PRs approved, awaiting merge
  ✅ Done:         {N} issues closed this session

Next action: {what Ralph will do next}
```

## Session State

Ralph state is session-scoped (not persisted):
- **Active/idle** — loop running or not
- **Round count** — check cycles completed
- **Scope** — categories to monitor (default: all)
- **Stats** — issues closed, PRs merged, items processed

## Integration

After coordinator's post-work follow-up assessment, if Ralph is active, immediately run the work-check cycle. Do NOT return control to the user. Keep the pipeline moving until the board is clear.

## Three Layers

| Layer | When | How |
|-------|------|-----|
| In-session | At the keyboard | "Ralph, go" — active loop |
| Local watchdog | Away, machine on | `npx @bradygaster/squad-cli watch --interval 10` |
| Cloud heartbeat | Unattended | `squad-heartbeat.yml` (event-based) |
