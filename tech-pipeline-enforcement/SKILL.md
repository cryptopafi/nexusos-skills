---
name: tech-pipeline-enforcement
description: Use to enforce TECH IL-11/IL-12/IL-13 rules: grep-verify edits, runtime test, test all consumers
---

# Problema
TECH pipeline lacked enforcement for dead code cleanup, phased execution, post-edit verification, rename thoroughness, commit metadata, and context budget. Source: @iamfakeguru (29-30% false task complete rate) and OMC audit.

# Procedura
IL-14: Step 0 Rule + Phased Execution (max 5 files) + Post-Edit Verification (stack-specific)
IL-15: 8-type rename search protocol (JS/TS with Python/bash equivalents)
IL-16: 5 commit trailers (Confidence, Constraint, Rejected, Scope-risk, Not-tested)
IL-17: Context budget (outline >200L files, max 5 parallel reads, 500KB limit)

# Enforcement Loop
IL-16 E2E tested via git log trailers. OMC audit 4.0/4.0 PASS. SOUL.md updated to 17 immutable rules.
