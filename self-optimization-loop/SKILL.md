---
name: self-optimization-loop
description: Full NexusOS Self-Optimization Loop (SOL) procedure for continuous prompt improvement: discover, audit, build, approve, apply, track, and persist prompt optimizations.
argument-hint: <prompt target, queue item, or SOL operation>
trigger: /sol
source_procedure: /Users/pafi/.nexus/procedures/SELF-OPTIMIZATION-LOOP.md
---

# Self-Optimization Loop (SOL)

Use this skill when Pafi asks for the complete SOL procedure, SOL governance, SOL prompt optimization workflow, or implementation details for the NexusOS self-optimization loop.

This is distinct from `/sol-cycle`:
- `self-optimization-loop` is the complete SOL procedure and governance workflow.
- `sol-cycle` is the runtime skill for executing one queue item through audit, validation, approval, apply, and Cortex save.

## Canonical Procedure

Read and follow the complete imported procedure at:

`references/SELF-OPTIMIZATION-LOOP.md`

The reference file is an exact copy of the canonical NexusOS procedure from:

`/Users/pafi/.nexus/procedures/SELF-OPTIMIZATION-LOOP.md`

## Execution Rules

1. Before modifying prompts or SOL infrastructure, read the canonical procedure reference.
2. Use the procedure's phase model: Discover -> Audit -> Build -> Approve -> Apply -> Track.
3. Preserve schema, safety rails, approval gates, Cortex persistence, and manifest/queue behavior exactly unless Pafi explicitly asks for a procedure update.
4. For one-item runtime execution, delegate to the separate `/sol-cycle` workflow after confirming the queue/audit state.
5. If the canonical procedure and runtime skill disagree, treat the canonical procedure as policy and the runtime skill as implementation detail.
