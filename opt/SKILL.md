---
name: opt
description: "Optimize any prompt or text using the latest available PromptForge pipeline. Classifies input, selects PE techniques, runs multi-phase optimization (SCOPE, Optimize, Structure, Score), and delivers the improved version. Use when the user says 'opt', '/opt [text]', '[$opt]', 'optimize this prompt', or wants to improve any prompt/instruction/system message."
argument-hint: <prompt text to optimize>
model: claude-opus-4-7
forge_version: "4.0"
---

# /opt — PromptForge Optimizer

Optimize any prompt, instruction, or text block using the full PromptForge v4.0 pipeline with PE technique selection.

## Freshness Rule

Before using this skill, resolve the newest/highest-capability local copy if multiple `opt` skills exist. Check these locations when available and follow the copy with the highest `forge_version`, then newest mtime, then richest explicit trigger/source-of-truth rules:
- `~/.codex/skills/opt/SKILL.md`
- `~/.agents/skills/opt/SKILL.md`
- `~/.claude/projects/-Users-pafi/skills/opt/SKILL.md`
- `~/.nexus/library/repos/nexusos-skills/opt/SKILL.md`

If an explicit path is attached by Pafi, read it, but still compare against the newer NexusOS/Codex copies before delivering. State when a supplied copy is stale.

## Source Of Truth

Load these files when using this skill, unless they are already loaded in the current session:
- `~/.nexus/procedures/PROMPTING.md`
- `~/.claude/projects/-Users-pafi/memory/promptforge.md`
- `~/.nexus/prompt-library/methodology/promptforge.md` if present
- `~/.claude/projects/-Users-pafi/memory/feedback_never_skip_explicit_skill.md` if present
- `~/.claude/projects/-Users-pafi/memory/rules/rules-hard.md` sections `PROMPT-H-002` and `OPT-ALWAYS` if present
- `~/.claude/projects/-Users-pafi/memory/rules/rules-standard.md` section `COM-S-004` if present

If a source file cannot be read, continue with the best available PromptForge behavior and state which reference was unavailable.

## Trigger Behavior

- Plain `opt`, `/opt`, `[$opt]`, or `optimize`: optimize only. Do not execute the optimized task.
- `opt explain` or `/opt explain`: optimize only, plus scoring and applied techniques.
- Explicit skill invocation wins over task interpretation. If the text looks like a work request, still optimize the request rather than doing the work.
- For non-trivial prompts outside explicit `opt`, apply PromptForge silently when useful, but do not show scoring unless Pafi asks.

## When NOT to Use

Do NOT invoke this skill automatically when:
- The user asks to *run* or *execute* a prompt (not optimize it) — just run it directly
- The user wants code written or a task completed — this skill only improves prompts, it does not execute them
- The input is a finished product being reviewed for correctness, not quality of wording
- The user says "summarize this" or "explain this" — those are not optimization requests

If Pafi explicitly invokes `opt`, `/opt`, `[$opt]`, or `optimize`, the explicit trigger overrides this section and the task is optimized, not executed.

## Arguments

The user provides text to optimize. This can be:
- A raw prompt or instruction
- A system message or agent brief
- Any text that would benefit from prompt engineering optimization
- If no text is provided, ask the user what they want to optimize

## Input Validation

Before running the pipeline, validate the input:

| Check | Condition | Action |
|-------|-----------|--------|
| Empty input | No text provided after `/opt` | Ask the user: "What would you like to optimize?" |
| Too short | Input is fewer than 5 words | Classify as TRIVIAL and tell the user |
| Non-text input | Input is code only (no natural language) | Warn the user; offer to optimize the docstring or comments instead |
| Already optimized | Input contains PromptForge score block | Ask if they want to re-optimize from the existing version |
| Language mismatch | Input is not in English | Optimize in the input language; score labels may remain in Romanian per pipeline spec |

If validation fails and cannot be resolved, stop and report the issue clearly — do not attempt optimization on invalid input.

## Model Routing

This skill is pinned to `claude-opus-4-7` (extended thinking enabled) per MODEL ROUTING and OPUS PLAN HARD rules. Prompt optimization is architecture-class reasoning — multi-phase pipeline, technique stacking, self-calibration on PRODUCTION runs require Opus-tier depth.

**Stacking rule:** STANDARD = 1-2 techniques · COMPLEX = 3-4 (must combine reasoning + structure + verification families) · PRODUCTION = 4-6 (must include CRITIC or Cognitive Verifier).

**Fallback when Opus 100M cap is exhausted:**
- User invokes `/opt --model sonnet <text>` to force Sonnet for a single run.
- Pipeline still completes end-to-end; expect score ceiling ~78/100 on COMPLEX and reduced calibration on PRODUCTION.
- Cap status: `~/.claude/check-usage-v2.sh`.
- Never silently downgrade — always emit `⚠ Sonnet fallback active — Opus cap reached` in Step 5 output.

## Execution

Follow the PROMPTING master procedure (`~/.nexus/procedures/PROMPTING.md`).
If `PROMPTING.md` is missing or unreadable, proceed with the inline steps below as the authoritative fallback:

### Step 1: Classify
Classify the input using the Classification Gate (Pas 1):
- **TRIVIAL**: Skip — tell the user the prompt is too simple to optimize
- **STANDARD**: Run LIGHT path (phases 1→2→3→4), select 1-3 techniques
- **COMPLEX**: Run FULL path (phases -1→0→1→2→3→4→5), select 3-6 techniques
- **PRODUCTION**: Run FULL + phase 6 (Cortex persistence), include C-072 (Self-Calibration) and C-073 (Consistency Check)

### Step 2: Cortex Pre-Search
Search Cortex for existing high-scoring variants before crafting:
```
cortex_search(query="<prompt summary>", collection="procedures", limit=3)
```
- Score ≥ 0.8 → use as base, skip to technique selection (recency check: reject if > 30 days old)
- Score ≥ 0.5 → use as starting point
- Score < 0.5 → build from scratch

### Step 3: Technique Selection
Select techniques from the Pas 3 decision tree based on task type:
- Reasoning/Analysis → C-058 Few-Shot CoT, C-062 Step-Back
- Creative/Generation → C-042 Persona, C-053 Outline Expansion
- Code/Technical → C-068 CRITIC, C-059 ReAct
- Complex multi-step → C-050 Recipe, C-044 Cognitive Verifier
- Ambiguous/Vague → C-070 Intention, C-067 RAR
- Agentic/Tool-Use → C-059 ReAct, C-075 Planning Phase

### Step 4: PromptForge Pipeline
Run the selected phases:

| Phase | Action | WHY |
|-------|--------|-----|
| -1 | Intent Extraction (if COMPLEX) | Surfaces hidden goals before committing to approach |
| 0 | Step-Back abstraction (if ambiguous) | Reframes the problem to avoid local optima |
| 1 | SCOPE: ask up to 5 clarifying questions (or infer from context) | Resolves ambiguity before optimization wastes effort |
| 2 | Optimize: apply selected techniques | Core transformation |
| 3 | Structure: XML tags for Claude, markdown for others | Maximizes parser/model compatibility |
| 4 | Score: 5 dimensions × 0-20 = /100 | Forces explicit quality evidence before delivery |
| 5 | Meta-Prompting: if score < 85 (STANDARD/COMPLEX) or < 90 (PRODUCTION), re-optimize weakest dimension (max 3 iterations). WHY: floor 70 ships B-grade prompts. | Catches sub-threshold output before it ships |
| 6 | Cortex Save (PRODUCTION only) | Persists high-quality patterns for reuse |

### Pre-Deliver Checklist (P15 Verify-Before-Deliver)
Before emitting output, confirm:
- [ ] Classification justified with evidence from input (not assumed)
- [ ] Techniques mapped to specific weaknesses identified in the prompt
- [ ] All 5 dimensions scored with explicit evidence, not assertion
- [ ] Optimized prompt does not exceed 2× input length unless COMPLEX/PRODUCTION
- [ ] No technique stuffing — max 3 new techniques per run for STANDARD

### Step 5: Deliver

Output format:
```
🔧 PromptForge v4.0 | Class: {CLASS} | Techniques: {list}

## Optimized Prompt

{the optimized prompt, ready to copy-paste}

## Score: {X}/100
- Claritate: {x}/20
- Completitudine: {x}/20
- Corectitudine: {x}/20
- Focalizare: {x}/20
- Adecvare agent: {x}/20

## Techniques Applied
{brief explanation of each technique and why it was chosen}

## Key Changes (before → after)
- {3-5 bullets: what changed and why it improves the prompt}
```

### Step 6: Cortex Save (PRODUCTION class only)
Save the optimization session to Cortex (collection: `procedures`, type: `promptforge-pattern`) with score, techniques, and task type metadata. Skip this step for STANDARD and COMPLEX classes unless explicitly requested.

## Worked Example (P55 Show-Don't-Tell)

**Input (raw):** "Write email to client about project delay"

**Classification:** STANDARD (single task, clear intent, <10 words)

**Techniques selected:** C-042 Persona + C-053 Outline Expansion

**Optimized output:**
```
You are a senior account manager writing a client-facing delay notification.

Context: [Project name], originally due [date], will now deliver by [new date].
Reason: [1-sentence cause].

Email structure:
1. Acknowledge the delay directly (no hedging)
2. State revised timeline and next milestone
3. Offer one concrete mitigation action
4. Close with confidence, not apology

Tone: professional, direct, not defensive. Under 150 words.
```

**Score:** 81/100 (Claritate 17 · Completitudine 16 · Corectitudine 17 · Focalizare 16 · Adecvare 15)

**Bad output (P23 — what NOT to do):**
Rewriting the user's task as a finished email — that executes the prompt, it does not optimize it.

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Input is a single word | Classify TRIVIAL; tell user it's too short to optimize meaningfully |
| Input is already a high-quality prompt (score would be ≥ 90) | Run pipeline, deliver result, note minimal gains in output |
| PROMPTING.md exists but is malformed or empty | Fall back to inline steps; log warning in output |
| Cortex pre-search returns a match but techniques differ from current task type | Use Cortex base but override technique selection with current task type logic |
| Meta-prompting runs 2 iterations and score is still < 70 | Deliver with explicit warning: "Score {X}/100 — below target after 2 refinement rounds" |
| User provides both `/opt` and explicit technique names (e.g. "use CoT") | Honor user-specified techniques; append to selection rather than replace |
| Input is a PromptForge output block from a previous `/opt` run | Ask: "Re-optimize from this version, or start fresh?" |
| PRODUCTION class requested but Cortex is unreachable | Complete pipeline through phase 5; skip phase 6; warn that session was not persisted |

## Error Contract

| Error | Cause | Response | Fallback |
|-------|-------|----------|----------|
| `PROMPTING_MD_MISSING` | `~/.nexus/procedures/PROMPTING.md` not found or unreadable | Warn user; proceed with inline pipeline | Inline steps are authoritative fallback |
| `CORTEX_UNREACHABLE` | Cortex search or save call fails | Skip pre-search; build from scratch; skip phase 6 | Never block — deliver optimized prompt without Cortex |
| `SCORE_BELOW_TARGET` | Score < 70 after 2 meta-prompting iterations | Deliver with warning banner in output | No further retries; user may re-invoke |
| `INVALID_INPUT` | Input fails validation (empty, code-only, etc.) | Stop; report specific validation failure | Ask user to supply valid text |
| `CLASSIFICATION_AMBIGUOUS` | Input could be STANDARD or COMPLEX | Default to COMPLEX; note assumption in output | User may override with explicit class hint |

All errors are non-blocking unless input is invalid. A degraded optimized prompt is always better than no output.

## Error Handling

- If Cortex is unreachable, skip pre-search and proceed from scratch
- If score stays < 70 after 2 meta-prompting rounds, deliver with warning
- Never block — a degraded optimized prompt is better than no prompt

## Examples

```
/opt Write a Python script that scrapes Instagram
/opt Create a system prompt for a customer service chatbot
/opt Build a Claude Code skill that monitors API uptime
```
