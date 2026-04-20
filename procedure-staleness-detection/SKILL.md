---
name: procedure-staleness-detection
description: Use to detect and flag silently degraded or outdated modular procedures in the LEGO library
---

Modular procedures can silently degrade or become outdated without anyone noticing. No enforcement mechanism existed to ensure regular review and updates of LEGO components (skills, patterns, plugins).

Pafi asked: how do we make sure procedures don't get forgotten? Answer: triple enforcement — session gate + pre-use check + auto-scan. Zero procedures can be silently forgotten.

Solution: Triple enforcement: 1) SESSION GATE — at every session start (Step 6 briefing), read procedure-health.json and report any non-FRESH procedures. Cannot be skipped.; 2) PRE-USE CHECK — before applying any modular procedure, verify its status. FRESH=go, NEEDS_PARTIAL=warn+proceed, NEEDS_TOTAL=warn+ask, DEGRADED=fallback, BROKEN=stop.; 3) CODEX DELIVERY HOOK — when auditing Codex deliveries that modify LEGO components, auto-run procedure-health-check.sh --update-component to flag dependent procedures.
