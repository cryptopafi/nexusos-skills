---
type: procedure
created: 2026-03-22
status: active
slug: self-optimization-loop
tags: [procedure, nexus]
---

# Self-Optimization Loop (SOL) v2.0

**Status**: ACTIVE
**Creat**: 2026-03-09
**Updated**: 2026-04-09 (v2.0: SOL-on-SOL R5. Stale refs fixed, P74 early-exit, P79 motivation, P70 context budget, pattern checklist expanded P1-P81, PromptForge v4.0)
**Owner**: Genie
**Scope**: Continuous self-improvement of all LLM prompts across the Nexus system — agent prompts, SOUL.md files, production Gemini prompts, and system instructions.
**Trigger**: Weekly auto-discovery (Sunday 22:00) + on-demand via `optimize audit` or `optimize all`

> **v1.1 note**: Phase 1 (Discover) is fully automated via LaunchAgent. Phases 2-6 (Audit→Build→Approve→Apply→Track) are executed manually by Genie within Claude Code sessions, using Opus subagents for audit and Sonnet for building. This is by design — these phases require model access that cannot run from a standalone Python script.

---

## 1. Problema

Prompts degrade silently. New patterns are discovered (81 patterns, P1-P81) but never retroactively applied to existing prompts. Production prompts in scripts get written once and never revisited. Without a systematic loop, the system's prompt quality drifts downward over time while the knowledge of what good prompts look like grows.

## 2. Architecture

```
DISCOVER (Python, weekly) → AUDIT (Opus subagent) → BUILD (Sonnet) → APPROVE → APPLY → TRACK
```

| Phase | Actor | Input | Output |
|-------|-------|-------|--------|
| Discover | `prompt-optimizer-discover.py` | Agent prompts + SOUL.md + scripts + sync | `manifest.json` + `queue.json` |
| Audit | Opus subagent | Prompt text + 81 PE patterns (P1-P81) + PromptForge rubric | Audit JSON (scores, gaps, recommendations) |
| Build | Sonnet (Genie) | Audit JSON + original prompt | Improved prompt in `staged/` |
| Approve | Auto or Pafi | Staged prompt + score delta | APPROVED / REJECTED |
| Apply | Genie | Approved prompt | Written to source file |
| Track | Genie | All above | `history/` + Cortex + manifest update |

## 3. Procedura

### Pas 1: Discover

Run `~/.nexus/scripts/prompt-optimizer-discover.py`. This:
- Scans `~/.claude/projects/-Users-pafi/memory/agent-prompts/*.md` for agent prompts
- Scans `~/.nexus/agents/*/SOUL.md` for soul prompts
- Scans `~/.nexus/scripts/*.py` and `~/.nexus/sync/*.py` for function-based LLM prompts
- Self-excludes discovery script and benchmark tools (EXCLUDED_SCRIPTS)
- Uses file lock to prevent concurrent runs
- Merges with existing `manifest.json` (preserves audit history)
- Generates `queue.json` with top 5 prompts to audit, prioritized by (P21 weighted):
  1. **Unaudited** (never seen) — weight: 100 (always first)
  2. **Changed since last audit** (content hash mismatch) — weight: 80
  3. **Lowest score** (< 70) — weight: 60 + (70 - score) (lower score = higher priority)
  4. **Oldest audit** (periodic refresh) — weight: 40 + days_since_audit/7
  5. **High-traffic** (invoked frequently since last audit) — weight: 50 + invocation_count/10 (read from manifest.json `invocation_count` field if available; skip if not tracked)

### Pas 2: Audit (Opus Subagent)

For each prompt in `queue.json`, launch an Opus subagent with this brief:

```
Audit this LLM prompt against our 81 PE patterns (P1-P81) and PromptForge v4.0 scoring rubric.

PROMPT TO AUDIT:
<prompt text>

SCORING RUBRIC (5 dimensions, 0-20 each, total 100):
- D1 Claritate: Orice agent înțelege identic din prima citire
- D2 Completitudine: Tot contextul necesar este prezent
- D3 Corectitudine: Nicio presupunere falsă sau constrângere greșită
- D4 Focalizare: Un singur obiectiv principal, fără dispersie
- D5 Adecvare agent: Construit exact pentru capacitățile agentului țintă

SCORING CALIBRATION ANCHORS (use these to calibrate your scores):

Score ~40 (FAIL): "Summarize this text" — no role, no output format, no constraints, no context.
Score ~60 (CONDITIONAL): "You are a technical writer. Summarize the following text in 3 bullet points, focusing on key decisions." — has role + output format but no few-shot, no edge cases, no grounding.
Score ~80 (PASS): "You are a technical writer for NexusOS documentation. Given a session transcript, produce a 3-bullet summary. Each bullet: max 15 words, starts with action verb. Focus on: decisions made, bugs fixed, features added. Ignore: small talk, debugging attempts that failed. Example good bullet: 'Fixed ECHELON YouTube scraper timeout by adding 30s retry.' Example bad bullet: 'We talked about fixing things.'" — has role + output format + constraints + negative examples + few-shot + domain grounding.

PATTERNS TO CHECK (report which are present vs missing — check PATTERN-INDEX.md for full definitions):
Core (P1-P24): P6 Permission Framing | P7 Classification Gate | P8 Negative Space | P10 CoT (zero-shot first) | P15 Verify-Before-Deliver | P17 Stress-Test | P18 Plan-Before-Solve | P20 Stable/Dynamic (3-tier) | P21 Ranking | P23 Negative Examples | P24 Schema-First
Agentic (P25-P35): P25 Anti-Affirmation | P26 Tiered Autonomy | P29 Identity Anchor | P33 Conciseness Hard
Coding (P48-P54): P48 Severity-Tiered | P49 Spec-First | P50 Debug RIHV | P53 Language Constraints
Creative (P55-P69): P55 Show-Don't-Tell | P56 Voice Capture | P62 Self-Consistency
New (P70-P81): P70 Context Engineering | P72 CLoT | P74 Early Exit | P76 Brain/Hands/Session | P77 Utility-Guided | P79 Instruction Motivation | P80 Trace Compliance

Also check for: Role Assignment, Output Blueprint, Few-Shot Examples,
Chain-of-Thought, Decomposition, Negative Space (out-of-scope definition),
Grounding Instructions, Permission Framing.

DOMAIN-SPECIFIC PRIORITY (P9 — score the most impactful patterns first):
- Agent prompts (SOUL.md, agent-prompts/): Prioritize P2 Role Assignment, P8 Negative Space, P23 Negative Examples. These define agent identity.
- Production script prompts (scripts/*.py): Prioritize P24 Schema-First, P20 Stable/Dynamic Split, P4 Output Blueprint. These affect API reliability.
- Orchestrator prompts (CLAUDE.md sections): Prioritize P18 Plan-Before-Solve, P7 Decomposition, P15 Verify-Before-Deliver. These affect workflow correctness.

REASONING REQUIREMENT: For each dimension, explain your reasoning BEFORE assigning a score. State what evidence you found (or didn't find) in the prompt, then assign the score. Do not just list numbers — justify each one.

OUTPUT FORMAT (JSON):
{
  "scores": {"D1": N, "D2": N, "D3": N, "D4": N, "D5": N, "total": N},
  "reasoning": {
    "D1": "Evidence: [what you found]. Score: N because [justification].",
    "D2": "...", "D3": "...", "D4": "...", "D5": "..."
  },
  "techniques_present": ["list"],
  "techniques_missing": ["list"],
  "recommendations": [
    {"priority": "HIGH|MEDIUM|LOW", "technique": "name", "reason": "why", "suggestion": "concrete fix", "confidence": "HIGH|MEDIUM|LOW"}
  ],
  "verdict": "PASS|CONDITIONAL|FAIL",
  "counter_argument": "string (required if initial total > 80, else null)"
}

reasoning field cap: max 40 words per dimension. If evidence requires more, summarize to the single most important finding.

ASSUMPTION CHALLENGE (P17): After scoring all 5 dimensions, re-read your D3 (Context) and D4 (Constraints) scores. Ask yourself: "Am I giving credit for implied context that isn't actually written?" If yes, reduce by 1-2 points. Prompts should be self-contained — don't assume the model knows things it hasn't been told.

ANTI-AFFIRMATION GATE (P25): If your initial total score exceeds 80, you MUST generate one counter-argument that lowers the score by 5-10 points, then reconcile and justify your final score. Do not skip this step — it is the structural guard against sycophantic auditing. Log the counter-argument in a "counter_argument" field in the JSON output.

Be rigorous. Score honestly — do not inflate. A score of 60 is acceptable for simple prompts. Use the calibration anchors above to ground your scores.
```

**Context budget (P70)**: If the prompt being audited exceeds 200 lines, chunk it into logical sections and audit each against relevant patterns. Summarize cross-section findings at the end. Do not load the full 81-pattern checklist for TRIVIAL/SIMPLE prompts — use the 8-technique base catalog (PromptForge §3.1) (~/.nexus/procedures/PROMPTING.md §3.1) instead.

Save audit output to `~/.nexus/optimization/history/<prompt-id-sanitized>/<date>-audit.json`.

### Pas 2.5: Early Exit Gate (P74)

If audit score ≥ 85 AND all dimensions ≥ 16 AND verdict = PASS → skip Build phase. WHY: prompts above this threshold have diminishing returns from further optimization. Log as `SKIPPED_OPTIMIZED` in manifest and move to next prompt in queue.

### Pas 3: Build (Sonnet)

For each audit with verdict CONDITIONAL or FAIL, or with score < 85:

1. Read the audit recommendations (sorted by priority: HIGH first)
2. Read the original prompt
3. Apply each recommended technique following PromptForge v4.0 construction rules:
   - Add sections, not rewrite — preserve the original voice and structure
   - Respect the prompt's target model (Gemini prompts stay Gemini-compatible)
   - For production prompts: maintain the stable/dynamic split (P20)
4. Self-score the improved version
5. **VERIFY (P15)**: Re-run the audit brief (Pas 2) on the improved prompt. Compare scores. If any dimension DECREASED → revert that technique and try the next recommendation instead. WHY: without verify, technique stuffing and contradictions silently degrade prompts (see §7 Bad Cycle Example).
6. If score improved by < 5 points, iterate once (apply next recommendation)
6.5. **Trace Compliance (P80)**: Diff-check that the improved prompt contains structural markers for each HIGH-priority recommendation from the audit. For each HIGH rec that is missing from the improved prompt, either (a) apply it now, or (b) log the skip reason in a `skipped_recommendations` field in the staged file header. Silent skips are not permitted.
7. Write improved prompt to `~/.nexus/optimization/staged/<prompt-id-sanitized>.md`

### Pas 4: Approve

| Prompt type | Score delta | Approval |
|---|---|---|
| Agent prompt | >= +5, no dimension decreased | AUTO-APPLY |
| Agent prompt | < +5 or any dimension decreased | Pafi review via Telegram |
| Production prompt | Any change | Codex brief → Pafi review |

**Safety rails** (block auto-apply if ANY is true):
- Improved prompt is >50% different in char count from original
- Any Constraint or Safety section was removed or shortened
- The prompt's function signature or return format changed (production only)

### Pas 5: Apply

- Agent prompts: copy from `staged/` to `agent-prompts/`, overwriting original
- Production prompts: generate Codex brief with exact diff and file/line location
- Save original to `history/<prompt-id>/<date>-original.md` before overwriting

### Pas 6: Track

After each cycle:
1. Update `manifest.json`: new scores, audit date, version bump, increment `total_improvements`
2. **Re-run discover.py** to regenerate queue.json with fresh state (F4: prevents stale queue)
3. Save to Cortex: `collection=procedures, type=self-optimizer`
4. If 3+ prompts were optimized in this cycle, extract new patterns (following Session 1-5 methodology) (~/.nexus/procedures/PATTERN-INDEX.md §Pattern Discovery)
5. Emit VK: `✅ [SOL] cycle complete | audited: N | improved: M | avg_delta: +X.X | patterns: P`

---

## 4. Schedule

| Trigger | Action |
|---------|--------|
| Weekly Sunday 22:00 | LaunchAgent runs discover.py → manifest + queue |
| Monday session start | Genie reads queue.json in briefing, offers to run audit cycle |
| `optimize audit` command | Immediate: discover + audit top 5 |
| `optimize all` command | Immediate: discover + audit ALL prompts |
| `optimize <prompt-id>` | Immediate: audit + build one specific prompt |

## 5. Metrics

Track in manifest.json `meta` section:
- `avg_score`: rolling average across all audited prompts
- `total_improvements`: cumulative count of applied improvements
- `patterns_discovered`: total pattern count (currently 81)
- `cycle_count`: number of completed SOL cycles

**Success criteria**: avg_score increases by 2+ points per month.

---

## 6. Anti-Patterns

- **Over-optimization**: Do not optimize TRIVIAL prompts (< 100 chars, single-purpose). Skip them in discovery.
- **Technique stuffing**: Do not apply more than 3 new techniques per prompt per cycle. Diminishing returns above 3.
- **Format drift**: Production prompts must maintain their output JSON schema exactly. SOL improves the instruction, not the schema.
- **Circular optimization**: If a prompt has been optimized 3+ times with < 2 point improvement, mark as STABLE and skip for 30 days.

---

## 7. Complete Cycle Example (P1 Calibration)

This is a real SOL cycle from Cycle 2, showing the before/after for `agent/quality-gate`:

**BEFORE** (score: 72/100):
```
You are a quality gate agent. Review the delivery and determine if it passes or fails.
Check for correctness, completeness, and adherence to the brief.
Output: PASS or FAIL with explanation.
```
Missing: P1 (no examples), P8 (no out-of-scope), P23 (no negative examples), P24 (no schema).

**AFTER** (score: 82/100, delta: +10):
```
You are a quality gate agent for Codex deliveries. Review the delivery against the original task specification.

EVALUATION CRITERIA:
1. Correctness: Code works as specified. Partial implementation = FAIL.
2. Completeness: All acceptance criteria met. Missing any AC = FAIL.
3. Format: Output follows the required schema. Format deviation with correct logic = PASS.

EXAMPLES:
- PASS: "All 3 ACs met. Code compiles. Tests pass. Minor style nit (non-blocking)."
- FAIL: "AC #2 not implemented. Function returns string instead of JSON object."
- NOT YOUR JOB: Do not suggest improvements beyond the brief. Do not refactor. Do not add features.

OUTPUT: {"verdict": "PASS|FAIL", "details": "...", "blocking_issues": [...]}
```

**What improved**: +TASK_SPEC injection, +3 few-shot examples (PASS/FAIL/not-your-job), +completion rules (partial=FAIL, format-deviation=PASS), +output schema.

### Bad Cycle Example (P23 — what NOT to do)

**BEFORE** (score: 77/100, `agent/sales-outreach`):
```
You are a sales outreach specialist. Write personalized outreach messages...
```

**BAD optimization attempt** (score: 74/100, delta: **-3**):
Applied 5 techniques in one cycle (P2+P4+P8+P23+P24+P22) — technique stuffing. The prompt grew from 180 to 620 words. The added sections contradicted each other: "Always be brief" (from P4) but "Include 3 detailed examples" (from P1). Output schema changed from plain text to JSON, breaking downstream integration.

**Why it failed**:
1. Violated max 3 techniques per cycle (applied 5+)
2. Contradictory instructions (brief vs detailed)
3. Changed output format (format drift — §6 anti-pattern)
4. No verify step — regressions weren't caught before staging

**Correct approach** (score: 84/100, delta: +7):
Applied only P23 (negative examples) + P4 (structured follow-up format) + P22 (data freshness flags). Preserved original voice. Output format unchanged.

---

## 8. Integration

- **PromptForge v4.0**: SOL uses the same scoring rubric (D1-D5, 81 patterns P1-P81). Builder follows PromptForge construction rules. Phases 2-6 executed by Genie in Claude Code sessions (Opus audit, Sonnet build).
- **AUDIT-PRO**: SOL itself gets AUDIT-PRO'd periodically. Audit outputs follow compatible format.
- **PATTERN-INDEX**: `~/.nexus/prompt-library/patterns/PATTERN-INDEX.md` — source of truth for all 81 patterns. SOL Pas 2 checklist references this.
- **Cortex**: Reads patterns from `technical` collection. Writes cycle logs to `procedures` collection via `mcp__cortex__cortex_store`.
- **Discovery**: Phase 1 runs via `prompt-optimizer-discover.py` (LaunchAgent, weekly). Phases 2-6 require model access, executed manually by Genie.

---

## Changelog
- v2.1 (2026-04-24): SOL-on-SOL R6. +P25 anti-affirmation gate (counter_argument field required when initial score >80). +P80 trace compliance (Pas 3.6 diff-check, skipped_recommendations log). +P77 high-traffic queue weight (item 5, invocation_count). +P33 reasoning field cap (40 words/dimension). +inline paths for Session 1-5 and PromptForge §3.1 references.
- v2.0 (2026-04-09): **SOL-on-SOL R5 (major)**. PromptForge refs v3.7→v4.0, pattern count 69→81, Pas 2 checklist expanded with P55-P81 (creative, new research). +P74 early-exit gate (score ≥85 + all D≥16 → skip Build). +P79 motivation on Verify step. +P70 context budget for large prompts (>200L chunk, TRIVIAL use base catalog). Stale refs fixed: metrics 69→81, integration section cleaned (removed v1.1 note, unfulfilled v1.2 promise). Header date updated.
- v1.5 (2026-03-19): FORGE-AUDIT fixes applied: F1 PromptForge ref updated to v3.7 in Pas 3, F2 header bumped to v1.5, F3 architecture table pattern count updated to 81 PE patterns (P1-P81). Post-training alignment. Scoring dimensions aligned to PromptForge v4.0 (D1-D5 Claritate/Completitudine/Corectitudine/Focalizare/Adecvare). Pattern check list extended with P25-P35 agentic + P48-P54 coding.
- v1.4 (2026-03-19): SOL-on-SOL R4 (FINAL). +P17 assumption challenge (re-check D3/D4 for implied context). +P21 weighted queue priority (numeric weights for deterministic ordering). **STABLE** — delta +1.5 < threshold 2. Next SOL eligible: 2026-04-18.
- v1.3 (2026-03-19): SOL-on-SOL R3. +P15 verify-after-build (re-audit improved prompt, revert if any dimension decreased). +P9 domain-specific grounding (agent/production/orchestrator priority patterns). +P23 bad cycle example (technique stuffing → score regression).
- v1.2 (2026-03-19): SOL-on-SOL R1. +P6 scoring calibration anchors (40/60/80 examples) in audit brief. +P1 complete cycle example (§7, real quality-gate before/after). +P5 reasoning chain requirement (auditor must justify each score before assigning). +P22 confidence field on recommendations. PromptForge ref bumped to v3.5.
- v1.1 (2026-03-09): FORGE-AUDIT fixes F1-F9. Self-exclusion (F1), def-only detection (F5), fcntl lock (F6), expanded scan paths incl SOUL.md+sync/ (F7), metrics fields (F9), stale queue fix (F4), v1.1 disclaimer (F2), integration status clarified (F3).
- v1.0 (2026-03-09): Initial design. Discovery + Audit + Build + Approve + Apply + Track.
