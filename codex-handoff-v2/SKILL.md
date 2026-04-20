---
name: codex-handoff-v2
description: "Generate robust Codex handoff briefs with model routing"
---

Generate robust Codex handoff briefs with model routing

# Codex Handoff V2

## Purpose
Create self-contained Codex briefs with deterministic model selection and delivery metadata.

## Instructions
1. Choose model profile by complexity:
   - >500 lines: gpt-5.3-codex / xhigh
   - 100-500 lines: gpt-5.2-codex / medium
   - <100 lines: mini / low
2. Write brief to `~/.codex/genie-to-codex.md` with task, context, deliverables, constraints, and `## Execution Command` section (recommended Codex profile).
3. Set `~/.codex/handoff-status.json` to pending wit
