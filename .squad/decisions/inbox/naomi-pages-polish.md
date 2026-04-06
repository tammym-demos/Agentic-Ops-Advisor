# Decision: Demo Site Final Polish & Getting Started CTA

**By:** Naomi (Backend Dev)
**Date:** 2025-07-27
**Type:** Enhancement

## What
Final review and polish of `docs/index.html` as the demo entry point for Tammy's presentation. Added "Getting Started" section with quick-start terminal commands. Redesigned hero CTAs to prioritize the demo experience. Fixed hardcoded SP object ID in `scripts/grant-sp-permissions.sh`.

## Why
The demo site is the first thing the audience sees tomorrow. It needed a clear call-to-action that says "you can try this yourself" — the Getting Started section with a copy-paste terminal block provides that. The SP script had a non-existent app registration ID hardcoded, which would confuse anyone trying to use it.

## Changes
- **Nav:** Added "Demo" and "Get Started" links for better discoverability
- **Hero:** Primary CTA is now "Try the Demo" instead of "View on GitHub"
- **Getting Started section:** Clone → install → seed → run → test in 60 seconds
- **SP script:** Empty default + validation error with clear instructions

## Impact
- Low risk — additive changes only, no existing content removed
- Site tells a complete story: What → Why → How → Try It
- SP script now fails fast with helpful guidance instead of silently using a wrong ID
