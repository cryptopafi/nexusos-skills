---
name: parallel-agents
description: "Launch parallel subagent tasks safely with merge plan"
---

Launch parallel subagent tasks safely with merge plan

# Parallel Agents

## Purpose
Run 2-3 independent subagent lanes in parallel while avoiding state collisions.

## Instructions
1. Validate no write overlap across subtasks.
2. Create independent prompts with strict ownership boundaries.
3. Launch parallel execution in one orchestration step.
4. Collect outputs and run deterministic merge order.
5. Return consolidated result with lane provenance.

## Constraints
Do not parallelize tasks touching same mutable file set.
Do not merge unvalidated out
