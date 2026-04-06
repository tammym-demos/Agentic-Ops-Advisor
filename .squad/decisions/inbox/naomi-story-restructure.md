### 2025-07-27: Demo Story Arc Restructure — GitHub Pages
**By:** Naomi (Backend)
**What:** Restructured `docs/index.html` from a feature-list layout into a coherent 11-section demo story arc. Added 3 new sections (The Problem, Monitoring & Observability, Evaluations). Removed the standalone Capabilities section — its 6 cards were redistributed into the relevant story sections. Reordered sections to follow a narrative flow: problem → how it's built → where it runs → context layer → observability → quality gates → demo → getting started → tech stack → disclaimers.
**Why:** Tammy is presenting this as a demo tomorrow. The page needed to tell a story, not just list features. The new arc guides the audience from "here's the pain" through "here's how we built and govern the solution" to "try it yourself."
**Outcome:** ✅ Page restructured with all content preserved. No CSS changes needed — all new sections reuse existing class patterns. Nav updated with 10 links matching the new flow. SVG architecture diagram intact. All disclaimers preserved.
**Risk:** Low — purely presentational change. No backend, infrastructure, or test impact. All existing CSS classes reused.
**Impact:** Demo-ready page for Tammy's presentation. Story flows: Problem → GitHub → Azure → Work IQ → Monitoring → Evals → Demo → Get Started.
