---
name: five-steps-agents
description: |
  Architect multi-agent systems using the Five Steps Agents pattern (Boundaries, Signal Tiers, Error Handling, Tool Handling, Model Routing). Use when building any new multi-agent pipeline, skill with sub-agents, Claude Code agent, or agent orchestration system.
  ANTI-PATTERN: Do NOT use for single-agent tasks, simple prompt optimization, or non-agentic workflows.
version: 1.1.0
---

# Five Steps Agents

## Overview

Design and generate complete multi-agent systems by applying 5 mandatory architectural steps to every agent in the pipeline. Produces ready-to-deploy orchestrator + sub-agent files.

**Core Principle**: Every agent must have explicit boundaries, signal tiers, error handling, isolated tools, and optimal model routing. No exceptions.

## Procedure Reference
**Source**: `/Users/pafi/.nexus/procedures/FIVE-STEPS-AGENTS.md`
**Read the full procedure before executing.**

## Quick Summary

Five Steps Agents transforms a use case description into a complete multi-agent architecture. It starts with structured discovery questions (15 questions in 3 rounds), decomposes the system into distinct agents, applies the 5 mandatory steps to each agent, generates all files (orchestrator.md + sub-agent .md), validates against a 12-point checklist, and deploys.

## Input Validation

**Required before Phase 0 begins.** Abort with a clear error message if any required field is absent.

| Field | Required | Description |
|---|---|---|
| Use case description | YES | What the multi-agent system should accomplish (≥1 sentence) |
| Number of distinct responsibilities | YES (inferred or stated) | Must be ≥2; if 1 → exit and recommend single-agent template |
| Target deployment context | YES | Where agents will run (Claude Code, API, scheduled, etc.) |
| Budget / model cost constraint | NO | Informs model routing; defaults to cheapest viable if absent |
| Output format preference | NO | File artifacts vs inline; defaults to .md files |

**Validation failures**:
- Use case absent → ask user before proceeding
- Responsibilities = 1 → exit immediately, recommend single-agent template
- Deployment context absent → ask before Phase 2 (affects state management and alerting)

## Error Contract

| Error | Trigger | Response |
|---|---|---|
| Single-responsibility system | Gate Check detects ≤1 distinct agent cluster | Exit skill; output recommendation to use standard SOUL.md template |
| Intake incomplete | User skips required discovery questions | Pause; re-ask only the missing questions; do not proceed to Phase 1 with gaps |
| Template mismatch | Q15 matches a known pattern but template file is unreadable | Log the miss, proceed with generic decomposition, flag in output |
| Validation below threshold | Phase 4 checklist < 10/12 | Fix failures before deploying; do NOT emit VK on a FAIL run |
| File generation error | orchestrator.md or any sub-agent .md cannot be produced | Surface specific error to user; do not produce partial output silently |
| God-agent detected post-decomposition | Single agent has 3+ domain-crossing responsibilities | Trigger re-decomposition before proceeding to Phase 3 |

**Never drop silently.** Every error must surface to the user with the triggering condition and the required action.

## Output Contract

### On SUCCESS (validation ≥ 10/12)

| Artifact | Description |
|---|---|
| `orchestrator.md` | Coordinator system prompt, ≤1500 tokens |
| `{agent-name}.md` × N | Sub-agent system prompts, ≤800 tokens each |
| `AGENTS.md` | Routing + safety table (optional; required for 4+ agent systems) |
| Route command | Shell alias or `/route` registration for the orchestrator |
| Cortex entry | Architecture summary saved to Cortex with agent roster |
| VK | Validation Key emitted confirming PASS |

### On FAILURE (validation < 10/12 or intake blocked)

| Artifact | Description |
|---|---|
| Failure report | Lists which checklist items failed and required fixes |
| Partial drafts (if any) | Clearly labeled `[DRAFT — NOT DEPLOYABLE]` |
| No VK | VK is withheld until a passing validation run completes |

## Key Steps

1. **Phase 0 — Intake**: Ask structured discovery questions (Q1-Q15) to understand scope, constraints, and preferences. Skip Round 3 for simple pipelines (≤3 agents).
2. **Phase 1 — Decompose**: Break the system into distinct agents. Each agent = 1 responsibility cluster. Identify the orchestrator.
3. **Phase 2 — Architect**: Apply all 5 steps to each agent:
   - Step 1: Boundaries ("does" + "does NOT")
   - Step 2: Signal Tiers (HIGH/MED/LOW with specific criteria)
   - Step 3: Error Handling (flag incomplete, never drop; autonomous pipelines need alerting)
   - Step 4: Tool Handling (agent-specific, no overlap)
   - Step 5: Model Routing (Haiku ~1x, Sonnet ~5x, Opus ~30-60x cost — cheapest viable)
   - Phase 2b: Handoff Contracts (output Agent N = input Agent N+1, with status field)
   - Phase 2c: State Management (stateless default; persistent if scheduled/Q13=yes)
   - Phase 2d: Idempotency (safe re-runs, timestamps, dedup, lock files)
4. **Phase 3 — Generate**: Produce orchestrator.md (≤1500 tokens) + N sub-agent .md files (≤800 tokens each) + optional AGENTS.md and route command.
5. **Phase 4 — Validate**: Run 12-point checklist. Minimum 10/12 for PASS.
6. **Phase 5 — Deploy**: Place files, register route command, save to Cortex.

## Content Type Resolution

| Pipeline Type | Reference File | Key Focus |
|---|---|---|
| Lead Finder | `references/templates.md` § Lead Finder | Signal detection + enrichment + compilation |
| Client Onboarding | `references/templates.md` § Client Onboarding | Intake + provisioning + tracking |
| Content Pipeline | `references/templates.md` § Content Pipeline | Research + writing + queue management |
| Competitive Intel | `references/templates.md` § Competitive Intel | Monitoring + analysis + briefing |

**MANDATORY**: Read the relevant template section before proceeding when Q15 matches a known pattern.

## Workflow

### Step 1: Gate Check

Is this truly a multi-agent problem?
- **2+ distinct responsibilities** → YES → proceed
- **1 responsibility** → NO → recommend standard single-agent template, exit

### Step 2: Intake (Phase 0)

Ask discovery questions using the AskUserQuestion tool. Group into rounds:

**Round 1 (always)**: Q1-Q5 — scope, users, input, output, tasks
**Round 2 (always Q6-Q7; Q8-Q10 only for complex pipelines)**: deployment, budget + frequency, tools, error prefs
**Round 3 (4+ agents only)**: Q11-Q15 — integration, autonomy, state, success criteria, template match

**Skip rules**: Simple pipelines (≤3 agents) → R1 + Q6-Q7, skip Q8-Q15. Complex (4+) → all 3 rounds. Template match at Q15 → use template, ask only delta questions.

### Step 3: Decompose (Phase 1)

From answers, create agent roster table:
- Group responsibilities into agents (1 cluster = 1 agent)
- Identify orchestrator (coordinates, does NOT execute)
- If Q15 matched a template → load template from `references/templates.md`, adapt

**Branch-Then-Prune (P16)**: For systems with 4+ agents, propose 2-3 alternative decompositions and briefly justify which is best. Example: "Option A: 3 agents (signal+enrich+orchestrator) vs Option B: 4 agents (signal+enrich+qualify+orchestrator). Option A preferred — qualify is too thin to justify separate agent overhead."

**Merge Challenge (P17)**: After decomposition, ask: "Could any 2 agents be merged without violating the single-responsibility principle?" If yes and the merged agent stays under 800 tokens → merge. Fewer agents = less handoff overhead.

**Reasoning Requirement (P5)**: For each agent in the roster, write ONE sentence justifying why it's a separate agent (not merged with its neighbor). If you can't justify it → merge.

### Step 4: Architect (Phase 2)

For EACH agent, apply all 5 steps. Use GOOD/BAD calibration examples from the procedure.

For the orchestrator, additionally define:
- Workflow sequence
- Handoff format between agents
- Error escalation path
- Route command

### Step 5: Generate (Phase 3)

Produce files:
- `orchestrator.md` — coordinator system prompt (≤1500 tokens)
- `{agent-name}.md` × N — sub-agent system prompts (≤800 tokens each)
- `AGENTS.md` — routing + safety table (optional, for complex systems)

### Step 6: Validate (Phase 4)

Run 12-point checklist from procedure §Phase 4. Minimum 10/12. Fix any failures before proceeding.

### Step 7: Deploy and Report

Place files in target paths. Save architecture to Cortex. Emit VK.

## When to Use vs Alternatives

- **Five Steps Agents** (this): When building ANY multi-agent system with 2+ distinct agents that need coordination. Use for pipelines, orchestrated workflows, or agent teams.
- **Standard SOUL.md template**: When building a SINGLE agent with one responsibility. No orchestration needed.
- **Manual agent design**: When the system is experimental/throwaway and doesn't need the rigor of all 5 steps. Faster but lower quality.

## Quality Checklist

- [ ] All 5 steps applied to every agent (boundaries, tiers, errors, tools, routing)
- [ ] Every agent has explicit "You do NOT..." boundaries
- [ ] Signal tiers have concrete, measurable criteria (min 3 tiers, not binary)
- [ ] Error handling: "flag, don't drop" on every path
- [ ] If autonomous (Q2=automat): alerting mechanism defined, not just flagging
- [ ] Tool sets isolated per agent (no unjustified overlap)
- [ ] Model routing uses cheapest viable model per agent (with cost justification)
- [ ] Token budgets respected (SOUL ≤800, orchestrator ≤1500)
- [ ] Orchestrator coordinates only (does NOT execute agent tasks)
- [ ] Handoff contracts: output Agent N = input Agent N+1, with `status` field
- [ ] Idempotency: re-run safe, no duplicates, timestamped outputs
- [ ] State management: explicitly stateless OR persistent pattern implemented
- [ ] Validation checklist ≥ 10/12

## Common Pitfalls

1. **"God agent" anti-pattern**: One agent does everything. Fix: if an agent has 3+ "does" items from different domains, split it.
2. **All-Opus routing**: Using the most expensive model for every agent. Fix: default to Haiku, upgrade only with justification.
3. **Missing "does NOT" boundaries**: Agents step on each other's toes. Fix: for every "does" line, write a corresponding "does NOT" for the adjacent agent.
4. **No error handling = silent data loss**: Pipeline drops items without trace. Fix: every orchestrator MUST have "if sub-agent returns incomplete → flag as needs review."
5. **Binary signals**: Everything is "relevant" or "not." Fix: always use 3+ tiers with concrete criteria per tier.