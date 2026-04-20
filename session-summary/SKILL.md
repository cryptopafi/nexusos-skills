---
name: session-summary
description: "Generate and store session summary with completion metrics"
---

Generate and store session summary with completion metrics

# Session Summary

## Purpose
Capture completed work, decisions, and next actions at session end.

## Instructions
1. Summarize completed tasks and outcomes.
2. List saved skills/procedures and key decisions.
3. Add concrete next actions and blockers.
4. Store summary in Cortex `sessions` with metadata:
   `date`, `machine`, `skills_saved`, `tasks_completed`.
5. Return short human-readable recap.

## Constraints
Keep summary factual and concise.
Do not include secrets.
Do not skip blocker report
