# SRE Agent Integration — Architecture Decisions

**Author:** Holden (Lead)  
**Date:** 2025-07-27  
**Status:** DECIDED  
**Input:** Amos's ARM/Bicep research, Naomi's API surface research  
**Requested by:** Tammy

---

## Preamble

I reviewed both research documents in full, cross-referenced every recommendation against our existing codebase patterns (`sql_telemetry.py`, `work_context_stub.py`, `action_stub.py`, `work_context_mcp.py`, `agent/config.py`), and the team's decision history. My goal here is honest analysis, not rubber-stamping. Where I disagree with Amos or Naomi's recommendations, I say so.

Overall verdict: both research docs are solid work. Naomi's API surface mapping is particularly thorough. Most of their recommendations hold up. I have adjustments on phasing, flag design, and the memory push question.

---

## Decision 1: MCP Exposure Model

### Question
Should our MCP server be internet-accessible or VNet-restricted?

### Options

| Option | Pros | Cons |
|--------|------|------|
| **A. Internet-accessible + auth** | Simple setup; works immediately; demo-friendly | Wider attack surface; endpoint discoverable |
| **B. VNet-restricted** | Minimal attack surface; production-grade | Complex networking; unclear if SRE Agent supports VNet routing for outbound MCP; adds setup friction |
| **C. Internet-accessible now, VNet later** | Fast start; clear hardening path | Requires a future migration step |

### Analysis

SRE Agent connects *outbound* to MCP servers — it initiates the connection to our endpoint. The critical question is: can SRE Agent route to VNet-restricted endpoints? The docs say SRE Agent runs on a Container App (`Microsoft.App` resource provider) with a managed identity. There's no documented VNet injection or private endpoint support for SRE Agent's *outbound* MCP connections.

Our data is **synthetic**. Even the "production" version of this advisor uses synthetic telemetry. The security risk of exposing a read-only MCP endpoint that returns fake change events and synthetic runbook links is bounded.

That said, the right production pattern is zero-trust networking. We should plan for it even if we can't implement it today.

### Recommendation: **Option C — Internet-accessible now, VNet-restrict later**

- Deploy our MCP server with a public HTTPS endpoint
- Require Azure AD token validation on every request (not just "has a token" — validate audience, issuer, and tenant)
- Document the VNet hardening path for when SRE Agent's networking model is clearer
- Add an `MCP_REQUIRE_AUTH` environment variable (default: `true`) so local dev can skip auth

### Rationale
We can't VNet-restrict what we can't route. SRE Agent's outbound networking for MCP isn't documented well enough to guarantee private endpoint connectivity. Starting public with strong auth gives us a working demo and a clear hardening roadmap. This is not negligence — it's pragmatism with guard rails.

### Risk
If SRE Agent tokens don't include an audience claim we can validate, we'd need to fall back to shared secrets or API keys. Test this early.

---

## Decision 2: Bidirectional vs Unidirectional

### Question
Do we need BOTH patterns (MCP connector for SRE Agent → us, AND REST chat tool for us → SRE Agent)? Or is one direction sufficient?

### Options

| Option | What it enables | Complexity |
|--------|----------------|------------|
| **A. MCP only (SRE Agent → us)** | SRE Agent gets our change-context during its investigations | Low — extends existing `ENABLE_MCP` work |
| **B. REST only (us → SRE Agent)** | Our advisor delegates Azure-native triage to SRE Agent | Medium — new tool, undocumented API |
| **C. Both (bidirectional)** | Full complementary integration | Higher — two auth flows, two tool surfaces |

### Analysis

These directions serve fundamentally different purposes:

- **MCP (SRE Agent → us):** SRE Agent is investigating an incident. It calls our tools to get *organizational context* — who deployed what, what decisions were made, which runbook applies. **This is our unique value.** SRE Agent already has Azure Monitor, Resource Graph, and Kusto. It doesn't have change-context.

- **REST (us → SRE Agent):** Our advisor is analyzing a GPU spike. It asks SRE Agent "what do your Azure-native tools show for this cluster?" **This is SRE Agent's unique value.** We have synthetic telemetry. SRE Agent has live Azure diagnostics.

Both directions create value that the other can't. Naomi correctly identified this. **However** — and this is where I push back slightly — the REST chat API (`/api/v2/chat`) is **undocumented** (discovered via browser DevTools). Building production tooling on an undocumented API is fragile. It could change without notice.

The MCP connector, by contrast, is a **documented, supported** integration point with health monitoring and auto-recovery.

### Recommendation: **Option C — Both, but phased**

**Phase 1 (now):** MCP connector only. Extend `tools/work_context_mcp.py` to serve as the SRE Agent connector endpoint. This is low-risk, documented, and extends existing work.

**Phase 2 (after MCP is validated):** REST chat tool (`tools/sre_agent.py`). Build with synthetic fallback (following `work_context_stub.py` pattern). Accept the API fragility risk because the fallback ensures we always have a working demo.

**Phase 3 (optional):** Custom sub-agent registration via REST v2. This is a distribution mechanism, not a core integration. Deprioritize.

### Rationale
Phasing manages risk. We don't ship two untested integration surfaces simultaneously. MCP first because it's documented and closer to done. REST second because it's higher-risk (undocumented API) but higher-reward (bidirectional capability).

### Disagreement with Naomi
Naomi presented all three patterns (MCP, REST, sub-agent) at roughly equal priority. I'm explicitly sequencing them. The sub-agent pattern is interesting but premature — it adds value only *after* the MCP connector is working. Don't build the distribution mechanism before the product works.

---

## Decision 3: Auth Model

### Question
Should `tools/sre_agent.py` use `DefaultAzureCredential` (same as our other tools) or a separate service principal?

### Options

| Option | Pros | Cons |
|--------|------|------|
| **A. DefaultAzureCredential** | Consistent with all existing tools; no secret management; works with managed identity in Foundry | Shares identity with other tool surfaces |
| **B. Separate service principal** | Isolated blast radius; explicit SRE Agent permissions | Secret rotation; diverges from codebase pattern; adds auth complexity |
| **C. DefaultAzureCredential + dedicated RBAC** | Same credential, scoped permissions; consistent pattern | Slightly more RBAC config than (A) |

### Analysis

Our codebase uses `DefaultAzureCredential` **everywhere**: `serve.py` (line 182), `deploy_agent.py` (line 51), `run_foundry_agent.py` (lines 238, 340). The team has already burned significant time on auth issues — multiple P0 bugs traced to auth misconfiguration (see Holden history, Naomi history). Adding a different credential pattern increases the surface area for the exact class of bug we've struggled with most.

SRE Agent uses a custom resource ID (`59f0a04a-b322-4310-adc9-39ac41e9631e`), which is different from our existing scopes (`cognitiveservices.azure.com`, `management.azure.com`). But `DefaultAzureCredential.get_token()` handles arbitrary resource scopes — it's just a different string parameter.

The blast radius concern is real but addressable through RBAC, not separate credentials. Assign `SRE Agent Standard User` role (chat only) to our managed identity. This limits what the identity can do in SRE Agent without introducing a second credential.

### Recommendation: **Option C — DefaultAzureCredential with dedicated RBAC**

```python
from azure.identity import DefaultAzureCredential

SRE_AGENT_RESOURCE_ID = "59f0a04a-b322-4310-adc9-39ac41e9631e"

credential = DefaultAzureCredential()
token = credential.get_token(f"{SRE_AGENT_RESOURCE_ID}/.default")
```

- Same credential pattern as every other tool in the codebase
- `SRE Agent Standard User` RBAC role limits to chat-only access
- If we later need admin access (sub-agent registration), elevate the role — don't add a new credential
- Follow the existing per-request pattern (never create credential at module level / startup — see `lessons_learned/foundry-hosted-agent-deployment.md`)

### Rationale
"Same credential, right permissions" > "different credential, implicit permissions." Our auth history shows that credential divergence causes bugs. RBAC is the correct lever for permission scoping in Azure. Adding a service principal introduces secret management, rotation, and a second failure mode — none of which we need.

---

## Decision 4: Feature Flag Naming

### Question
Should we use `ENABLE_SRE_AGENT` as a separate flag from `ENABLE_MCP`? Or combine them?

### Options

| Option | Semantics | Orthogonality |
|--------|-----------|---------------|
| **A. Combine into `ENABLE_MCP`** | "MCP on = SRE Agent on" | ❌ Conflates MCP serving with SRE Agent querying |
| **B. Single `ENABLE_SRE_AGENT` for everything** | "SRE integration on/off" | ❌ Can't use MCP without SRE Agent |
| **C. `ENABLE_SRE_AGENT` (REST tool) + `ENABLE_MCP` (MCP server)** | Two independent capabilities | ✅ Orthogonal, composable |

### Analysis

The codebase has a clear pattern: **one flag per feature surface**.

- `ENABLE_WORK_IQ` controls the Work IQ context tool (`tools/work_context_stub.py`)
- `ENABLE_MCP` controls the MCP server wrapper (`tools/work_context_mcp.py`)

SRE Agent integration has two independent components:

1. **MCP connector (SRE Agent → us):** Already covered by `ENABLE_MCP`. When our MCP server is running, SRE Agent can connect. No new flag needed.

2. **REST chat tool (us → SRE Agent):** This is a **new tool surface** (`tools/sre_agent.py`). Following the established pattern, it gets its own flag.

Combining them would be semantically wrong. You might want `ENABLE_MCP=true` for non-SRE-Agent MCP clients. You might want `ENABLE_SRE_AGENT=true` without running an MCP server (just the REST chat tool).

### Recommendation: **Option C — Separate `ENABLE_SRE_AGENT` flag**

```python
# tools/sre_agent.py
ENABLE_SRE_AGENT: bool = os.getenv("ENABLE_SRE_AGENT", "false").lower() not in ("false", "0", "no")
```

Add to `agent/config.py` Settings dataclass:
```python
enable_sre_agent: bool = False
"""Enable SRE Agent REST integration tool (default: False)."""
```

Add to `.env.example`:
```
ENABLE_SRE_AGENT=false
```

### Rationale
Follows existing one-flag-per-surface convention. Keeps `ENABLE_MCP` semantically clean (it means "run the MCP server," not "integrate with SRE Agent"). Both flags default to `false` — no surprise behavior changes for existing deployments.

### Naomi's proposal validated
Naomi proposed `ENABLE_SRE_AGENT` as a separate flag. I agree with her reasoning. The naming follows our `ENABLE_` prefix convention. No changes needed to her proposal.

---

## Decision 5: Memory Push Strategy

### Question
Is it worth testing `#remember` via the chat API to push context into SRE Agent's memory? Or should we rely purely on the pull model (MCP connector)?

### Options

| Option | Value | Risk |
|--------|-------|------|
| **A. Push via `#remember` in chat API** | Pre-populates SRE Agent with organizational context | Undocumented; unverified; data staleness; no confirmation of storage |
| **B. Pull only (MCP connector)** | SRE Agent gets fresh context on demand | SRE Agent must decide to call our tools; context not available for general questions |
| **C. Push + Pull** | Best of both worlds | Maximum complexity; builds on unverified API |
| **D. Knowledge Base upload** | Documented; supports .md files; persistent | Portal-only; manual; up to 1000 files per agent |

### Analysis

Let me be direct: **building production features on `#remember` via the chat API is a bad idea.** Here's why:

1. **Unverified.** Naomi explicitly flagged this: "needs testing to verify `#remember` works via REST." We don't know if it works.
2. **Undocumented.** The memory commands (`#remember`, `#retrieve`, `#forget`) are documented as chat-interface commands, not API operations. There's no contract.
3. **Fire-and-forget.** We push data, get no confirmation it was stored, can't verify correctness, can't query what was remembered.
4. **Data staleness.** We push context at time T. Context changes at T+1. SRE Agent still has stale data. The pull model (MCP) always returns fresh data.
5. **Architecture smell.** Encoding operational context as chat messages to exploit a command prefix is a hack, not an integration pattern.

The MCP pull model is superior on every dimension except one: discoverability. If SRE Agent doesn't know to call our MCP tools, it won't get our context. But this is solved by the skill/instructions system — configure the SRE Agent's custom agent instructions to use our MCP tools for change-context questions.

### Recommendation: **Option B — Pull only (MCP connector). Do NOT build on `#remember`.**

- MCP connector provides fresh, on-demand context
- Configure SRE Agent instructions/skills to use our MCP tools for change-context questions
- If static organizational context is needed, use Knowledge Base upload (Option D) as a documented alternative
- File a feature request with the SRE Agent team for a proper memory/knowledge API

### One concession
A 30-minute spike to test whether `#remember` works via REST has value as a **research finding** — document whether it works, what the response looks like, and what the retention behavior is. But do NOT build production code around it. Log the finding in a research note and move on.

### Disagreement with Naomi
Naomi presented `#remember` via chat API as a "workaround" worth exploring. I'm being more definitive: **don't build on it.** The pull model is architecturally cleaner, documented, and reliable. The `#remember` hack is tempting because it feels like you're being proactive, but you're actually creating a maintenance liability with no observability.

---

## Cross-cutting: Alignment with Existing Patterns

I audited all four tool modules to verify my recommendations fit:

| Pattern | `sql_telemetry.py` | `work_context_stub.py` | `action_stub.py` | `work_context_mcp.py` | Proposed `sre_agent.py` |
|---------|--------------------|-----------------------|-------------------|----------------------|------------------------|
| Module-level config | ✅ `TELEMETRY_TABLES`, `_AGG_QUERIES` | ✅ `ENABLE_WORK_IQ`, synthetic data | ✅ Risk keywords | ✅ `_ENABLE_MCP` | ✅ `ENABLE_SRE_AGENT`, `SRE_AGENT_URL`, resource ID |
| Feature flag | N/A (always on) | `ENABLE_WORK_IQ` (default: true) | N/A (always on) | `ENABLE_MCP` (default: false) | `ENABLE_SRE_AGENT` (default: false) |
| Synthetic fallback | Implicit (data is always synthetic) | ✅ Returns `[]` when disabled | N/A (always synthetic) | Exits process when disabled | ✅ Returns synthetic SRE response when disabled |
| Auth | N/A (local DB) | N/A (no external calls) | N/A (no external calls) | N/A (stdio MCP) | `DefaultAzureCredential` + SRE Agent resource scope |
| Async | ✅ `async def query_telemetry` | Sync functions | Sync functions | Async MCP handlers | ✅ `async def query_sre_agent` (HTTP calls) |
| Disclaimer | ✅ Every response | ✅ `get_full_context` | ✅ Every response | Inherits from stub | ✅ Must include disclaimer |

The proposed `tools/sre_agent.py` follows established conventions. No pattern deviations needed.

---

## Phasing Summary

| Phase | Work | Flag | Risk |
|-------|------|------|------|
| **1 (now)** | MCP connector: extend `work_context_mcp.py` for SRE Agent, add auth validation | `ENABLE_MCP` | Low — documented integration point |
| **2 (next)** | REST chat tool: `tools/sre_agent.py` with synthetic fallback | `ENABLE_SRE_AGENT` | Medium — undocumented API |
| **3 (later)** | Custom sub-agent registration via REST v2 | `ENABLE_SRE_AGENT` | Low — documented API, but depends on Phase 1 |
| **Spike** | Test `#remember` via REST (30 min, research only) | N/A | None — just a finding |

---

## Agreement/Disagreement Register

| Topic | Amos | Naomi | Holden |
|-------|------|-------|--------|
| SRE Agent creation: portal prerequisite | ✅ Agree | — | ✅ Agree. Correct call. Don't fight undocumented IaC. |
| RBAC automation via Bicep | ✅ Agree | — | ✅ Agree. Automate what's automatable. |
| MCP connector as primary pattern | — | ✅ Agree | ✅ Agree. Highest value, lowest risk. |
| REST chat as secondary pattern | — | ✅ Agree | ⚠️ Agree with caveat: phase it, document API fragility risk |
| Sub-agent registration | — | ✅ (tertiary) | ⚠️ Deprioritize further. Phase 3, not Phase 2. |
| `#remember` via chat API | — | "worth testing" | ❌ Do not build on it. Quick spike for research only. |
| `DefaultAzureCredential` for auth | — | ✅ Proposed | ✅ Agree. Add RBAC scoping, not separate credential. |
| `ENABLE_SRE_AGENT` flag naming | — | ✅ Proposed | ✅ Agree. Orthogonal from `ENABLE_MCP`. |

---

## Action Items

1. **Naomi:** Extend `tools/work_context_mcp.py` with Azure AD token validation for incoming MCP connections (Phase 1)
2. **Naomi:** Build `tools/sre_agent.py` skeleton with synthetic fallback and `ENABLE_SRE_AGENT` flag (Phase 2)
3. **Amos:** Add `ENABLE_SRE_AGENT`, `SRE_AGENT_URL` to `.env.example`, `agent/config.py`, and `agent.yaml` environment list
4. **Amos:** Document SRE Agent portal creation steps in README or ops runbook
5. **Amos:** Add RBAC assignment Bicep module for SRE Agent managed identity → our resource group (Reader + Log Analytics Reader)
6. **Holden:** 30-minute spike to test `#remember` via REST — log finding, don't build on it
7. **Alex (Tester):** Test fixtures for `ENABLE_SRE_AGENT` flag (follow `conftest.py` pattern for `ENABLE_WORK_IQ`/`ENABLE_MCP`)

---

*"Good architecture is the art of making the right things easy and the wrong things hard. Building on undocumented APIs is neither."*
