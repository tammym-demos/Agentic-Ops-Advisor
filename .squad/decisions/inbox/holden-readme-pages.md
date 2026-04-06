# Decision: Add GitHub Pages brochure link to README

**Author:** Holden (Lead)  
**Date:** 2026-04-09  
**Status:** Implemented  

## Context
README audit (prior session) identified that the GitHub Pages site (`docs/index.html`) was not referenced anywhere in README.md. The brochure site covers architecture, Work IQ integration, evaluation framework, and the GitHub-to-Azure delivery pipeline — all key demo talking points.

## Decision
Added a single blockquote link (`> 🌐 **[Project Brochure Site](...)**`) immediately after the project description paragraph, before the Table of Contents. This mirrors the existing `> ⚠️` and `> ℹ️` disclaimer style.

## Rationale
- Demo is tomorrow — stakeholders need a one-click path to the polished overview
- Minimal change (1 line added), zero structural disruption
- Placed near the top for maximum visibility without cluttering the ToC

## Impact
- README.md: 1 line added (line 9)
- No code changes, no test impact
