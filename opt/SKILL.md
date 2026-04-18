---
name: opt
description: "Optimize any prompt or text using the PromptForge pipeline. Classifies input, selects PE techniques, runs multi-phase optimization (SCOPE, Optimize, Structure, Score), and delivers the improved version. Use when the user says '/opt [text]', 'optimize this prompt', or wants to improve any prompt/instruction/system message."
argument-hint: <prompt text to optimize>
---

# /opt — PromptForge Optimizer

Optimize any prompt, instruction, or text block using the full PromptForge v3.7 pipeline with PE technique selection.

## When NOT to Use

Do NOT invoke this skill when:
- The user asks to *run* or *execute* a prompt (not optimize it) — just run it directly
- The user wants code written or a task completed — this skill only improves prompts, it does not execute them
- The input is a finished product being reviewed for correctness, not quality of wording
- The user says "summarize this" or "explain this" — those are not optimization requests

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
- Score ≥ 0.7 → use as base, skip to technique selection
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

| Phase | Action |
|-------|--------|
| -1 | Intent Extraction (if COMPLEX) |
| 0 | Step-Back abstraction (if ambiguous) |
| 1 | SCOPE: ask up to 5 clarifying questions (or infer from context) |
| 2 | Optimize: apply selected techniques |
| 3 | Structure: XML tags for Claude, markdown for others |
| 4 | Score: 5 dimensions (Claritate, Completitudine, Corectitudine, Focalizare, Adecvare agent) × 0-20 = /100 |
| 5 | Meta-Prompting: if score < 70, re-optimize weakest dimension (max 2 iterations). Score ≥ 70 → proceed to delivery |
| 6 | Cortex Save: persist session to Cortex (PRODUCTION class only — includes C-072 Self-Calibration + C-073 Consistency Check) |

### Step 5: Deliver

Output format:
```
🔧 PromptForge v3.7 | Class: {CLASS} | Techniques: {list}

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
```

### Step 6: Cortex Save (PRODUCTION class only)
Save the optimization session to Cortex (collection: `procedures`, type: `promptforge-pattern`) with score, techniques, and task type metadata. Skip this step for STANDARD and COMPLEX classes unless explicitly requested.

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