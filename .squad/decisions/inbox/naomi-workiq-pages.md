# Decision: Work IQ Deep-Dive Section on GitHub Pages

**By:** Naomi (Backend Dev)
**Date:** 2025-07-27
**Status:** Implemented

## What
Added a dedicated Work IQ section to the GitHub Pages brochure site (`docs/index.html`), positioned between Features and Architecture. Includes value proposition, four context surface cards, MCP pattern explanation, hybrid advantage visual, and integrated disclaimer.

## Why
Tammy requested more prominent Work IQ coverage. Previous site had scattered, minimal mentions — no section explained what Work IQ is, how the agent uses it, or why it matters for the "telemetry + intent" narrative.

## Design Decisions
- **Placement:** Between Features and Architecture — after the reader knows what the agent does, before they see how it's built. Natural reading flow.
- **Style:** Reuses existing CSS patterns (feature cards, callout boxes) with purple accent (`--accent-purple`) to visually distinguish Work IQ from telemetry (blue) and actions (green).
- **MCP pattern:** Shown as a visual flow (Agent → MCP → Work IQ → Diagnosis) rather than code, keeping it accessible to non-technical readers.
- **Disclaimer:** Embedded directly in the section (not just in the global disclaimers) so readers encounter it in context.

## Risk
Low — additive HTML/CSS only, no behavior changes. Existing tests unaffected.
