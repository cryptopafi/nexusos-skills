---
name: audit-pro
description: "This skill provides a universal audit system with 9 audit types (code, procedure, skill, plugin, architecture, best-practices, config, prompt, portability), NPLF scoring, confidence filtering, and cross-model dispatch. Use when the user says 'audit this', 'review this code', 'check this procedure', 'FORGE-AUDIT', or when Claude detects quality issues in a file being discussed. Also triggers on Codex delivery notifications. Supports --light for quick single-pass Opus audit, --profile for domain-specific audit profiles, and --auto-fix for Ralph loop convergence. Do NOT trigger for: 'review this PR', 'review PR #NNN', 'check this pull request' (route to pr-review skill instead), 'fix this bug' (route to dev), 'explain how X works' (direct answer), 'rewrite section X' (direct edit)."
model: opus
color: red
allowed-tools: [Read, Grep, Glob, Write, Edit, Bash, Agent]
---

# Audit Pro Skill

## Step 0: Load Procedure

Read `${CLAUDE_PLUGIN_ROOT}/AUDIT-PRO.md` before doing anything else. This file is the single source of truth for all scoring rules, DSE definitions, fallback chain, and the 12-step procedura.

## Step 1: Resolve Target

The target may be:
- **Explicit** — user passed a file path, directory, or keyword (e.g., `this file`, `the script above`)
- **Implicit** — Claude detects quality issues in a file currently being discussed; use that file as target
- **Codex delivery** — a Codex task completion is reported in conversation; audit the delivered files immediately (per MEMORY.md reflex: "Codex delivery primit → AUDIT IMEDIAT, NU ÎNTREBA")

If target cannot be resolved unambiguously, ask once before proceeding.

## Step 2: Load Profile

Look for `--profile <name>` in the user's message. If present, load `${CLAUDE_PLUGIN_ROOT}/profiles/<name>.local.md`.

If no profile specified, auto-select based on subject type:

| Subject Type | Default Profile |
|-------------|----------------|
| procedure / SOP | `nexusos.local.md` |
| skill / SKILL.md | `default.local.md` (+ DSE-COMPAT auto) |
| plugin / plugin.json | `default.local.md` (+ DSE-COMPAT auto) |
| code (JS/TS/Python/Bash) | `code.local.md` |
| config / plist / .env | `default.local.md` |
| prompt / system.xml | `default.local.md` |
| architecture (multi-file) | `nexusos.local.md` |
| OpenClaw artifact | `openclaw.local.md` |

## Light Mode (`--light`)

If the user passes `--light` (or says "audit light", "quick audit", "audit rapid"):

**Shortcut: `--loop`** = alias for `--light --auto-fix`. Use when user says "audit loop", "loop audit", `/audit --loop target`.


**What it does:** Single-pass Opus audit. No cross-model, no confidence scorer. Ralph loop OFF by default but can be enabled with `--auto-fix`.

**Shortened flow:**
1. Resolve target (Step 1)
2. Load profile (Step 2) — or default
3. Classify tier (Step 3) — forced to STANDARD max (never DEEP in light mode)
4. Route → primary agent only (no secondary agents)
5. **SKIP** pre-flight model check (Opus only, always available)
6. **SKIP** sanitize (no cross-model dispatch)
7. Execute primary agent only → findings
8. **SKIP** confidence pass (report all findings as-is)
9. Score NPLF core only (no DSE unless explicitly requested)
10. Executive summary (compact: score + findings + verdict, no impact/recommendations)
11. Verdict
12. If `--auto-fix` also passed → **ENABLE Ralph loop** (light mode):
    - Opus re-audits (single-pass, same agent)
    - Sonnet fixes top 3 findings per iteration
    - Max 3 iterations, same convergence rules (PASS ≥3.5 + 0 CRITICAL + 0 HIGH, plateau δ<0.1)
    - Code targets: manual confirmation per iteration (same rule as full mode)
    - Non-code targets: auto-loop
    - **No cross-model, no confidence scorer** — just Opus audit + Sonnet fix cycle
    If `--auto-fix` NOT passed → **SKIP** Ralph loop (report and stop)

**Output:** Compact markdown — NPLF table + findings + verdict. No HTML, no Cortex log (unless `--cortex` also passed). If `--auto-fix`: shows iteration table (score progression per iteration).

**When to use:**
- `--light` alone: Quick quality check, mid-session review, pre-commit sanity check.
- `--light --auto-fix`: Fast convergence loop (~2-3 min per target). Best for batch procedure cleanup.

**Examples:**
```
/audit --light ~/.nexus/procedures/FORGEBUILD.md                    # quick check, no fix
/audit --light --auto-fix ~/.nexus/procedures/FORGEBUILD.md         # light + ralph loop
/audit --light --auto-fix ~/.nexus/audit/agents/code-auditor.md     # light + fix agent prompt
```

---

## Steps 3–12: Follow AUDIT-PRO.md §2 (Full Mode)

Do not duplicate the procedure here — execute §2 Steps 3–12 from `AUDIT-PRO.md` directly.

Quick reference of steps 3–12:

| Step | What | Key Rule |
|------|------|----------|
| 3 | CLASSIFY tier + DSE auto-detect | LIGHT (<50 lines), STANDARD (default), DEEP (--tier or multi-file) |
| 4 | ROUTE → agents + model | See routing table below |
| 5 | PRE-FLIGHT model availability | Fallback chain per §8 |
| 6 | SANITIZE if cross-model | Fail → Opus-solo fallback |
| 7 | EXECUTE agents (+ GPT-5.4 via `/audit-codex` if cross-model) | Parallel where safe |
| 8 | CONFIDENCE PASS | Suppress findings < 70; categories in `references/false-positive-categories.md` |
| 9 | SCORE | See scoring formula below |
| 10 | EXECUTIVE SUMMARY | Score + top 3 problems + top 3 quick wins + impact |
| 11 | VERDICT | PASS ≥3.5 / CONDITIONAL / FAIL |
| 12 | LOOP | Code = manual+confirm; non-code = Ralph auto |

## Routing Table — Subject Type → Agent

| Subject Type | Primary Agent | Secondary Agents | Model |
|-------------|--------------|-----------------|-------|
| code | `code-auditor` | `silent-failure-auditor`, `bestpractices-auditor` | Opus |
| procedure / SOP | `procedure-auditor` | `bestpractices-auditor` | Opus |
| skill (SKILL.md) | `skill-auditor` | `procedure-auditor` (structure), `bestpractices-auditor` | Opus |
| plugin | `plugin-auditor` | `skill-auditor` (if has SKILL.md) | Opus |
| architecture | `architecture-auditor` | `config-auditor`, `bestpractices-auditor` | Opus |
| best-practices | `bestpractices-auditor` | — | Opus |
| config / plist / .env | `config-auditor` | `silent-failure-auditor` | Opus |
| prompt / system prompt | `prompt-auditor` | — | Opus |
| portability check | `plugin-auditor` (DSE-COMPAT) | any primary agent | Opus |
| confidence scoring | `confidence-scorer` | — | Sonnet (support only, no finding authority) |

**Model ownership rule:** Opus produces ALL findings and verdicts. Sonnet (`confidence-scorer`) scores confidence on Opus findings only — never produces its own findings.

## Cross-Model GPT-5.4 Dispatch (Step 7 hook)

**ENFORCEMENT (HARD):** When `model-availability.sh` returns **CODEX_OPUS**, **GEMINI_OPUS**, or **FULL_TRIANGLE** AND `--light` was NOT passed, you **MUST** dispatch ALL available external models. Skipping an available model without a logged technical failure is a violation. Do NOT silently downgrade to Opus-solo.

When dispatching, run external models in parallel with Opus agents:

**GPT-5.4 dispatch** (when CODEX_OPUS or FULL_TRIANGLE):
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/codex-audit-dispatch.sh \
  --files "file1,file2,..." \
  --tier "${TIER}" \
  --timeout 300
```

**Gemini dispatch** (when GEMINI_OPUS or FULL_TRIANGLE):
```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/gemini-audit-dispatch.sh \
  --files "file1,file2,..." \
  --tier "${TIER}" \
  --timeout 300
```

Both scripts handle: auth/preflight check, sanitize, exponential backoff (1→2→4→8s), JSON validation, output archival. Each returns path to findings JSON file.

**Merge external findings with Opus findings at Step 8:**
1. Read JSON output from each dispatch script
2. Each finding gets `source: "gpt-5.4"` or `source: "gemini"` (enforced by schema)
3. Dedup by `file:line + category` — keep higher severity
4. Same `file:line` but different categories → keep both
5. Opus can CONFIRM / UPGRADE / DOWNGRADE / DISMISS each external finding

**If either dispatch fails:** Log warning, continue with remaining models. Never block audit for an external model failure.

## Finding Schema

Every finding must follow this schema (used for cross-model merge and Cortex logging):

```json
{
  "id": "F1",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "file": "/absolute/path",
  "line": 42,
  "category": "security|logic|naming|protocol|fitness|compat",
  "summary": "What is wrong (1 sentence)",
  "fix": "Concrete fix (actionable)",
  "confidence": 85,
  "source": "opus|gpt-5.4|gemini|sonnet"
}
```

Confidence < 70 → suppress from report. See `references/false-positive-categories.md` for category guidance.

## Scoring Formula (quick reference)

Full formula in `AUDIT-PRO.md` §Hybrid Scoring. Summary:

```
NPLF core score = mean(D1..D8) → /4.0
DSE score (if active) = mean(DSE dims) × 4/5 → /4.0

Combined:
  No DSE:  combined = NPLF_core
  1 DSE:   combined = (NPLF_core × 0.6) + (DSE × 0.4)
  2+ DSEs: combined = (NPLF_core × 0.5) + (avg(DSEs) × 0.5)

Blockers:
  Any core dimension at N-level (score 1) → max CONDITIONAL
  Best-practices pass_rate < 50% → add [BP-WARNING]
  Any DSE-COMPAT P-dimension < 2 → add [PORTABILITY-WARNING]

Verdict:
  ≥ 3.5 AND 0 critical AND no blockers → PASS
  2.5–3.4 OR has blockers OR 1 critical → CONDITIONAL
  < 2.5 → FAIL
  2+ CRITICAL findings → FAIL (override, regardless of combined score)
```

## Ralph Loop Convergence Criteria

- EXIT PASS: combined ≥ 3.5 AND 0 critical AND 0 high
- EXIT plateau: |score_new − score_prev| < 0.1
- EXIT max: iteration ≥ max_iterations (default 3)

State file: `~/.claude/audit-pro-loop.local.md` (runtime-only, auto-created, auto-deleted on completion, not committed).

## References (load on demand)

| Reference | When to load |
|-----------|-------------|
| `${CLAUDE_PLUGIN_ROOT}/references/nplf-calibration.md` | Scoring edge cases, calibrating dimension scores |
| `${CLAUDE_PLUGIN_ROOT}/references/false-positive-categories.md` | Step 8 confidence pass |
| `${CLAUDE_PLUGIN_ROOT}/references/dse-registry.md` | DSE auto-detect, profile DSE field lookup |
| `${CLAUDE_PLUGIN_ROOT}/references/anti-patterns.md` | Verifying "do NOT do this" list per agent |

Do not load references preemptively — only when the relevant step requires them.

## Output Contract

Every audit produces:
1. Markdown report (always) — order: Executive Summary → NPLF Core Dimensions → DSE Dimensions (if active) → Combined score + Verdict + flags → Findings by Severity → Recommendations → Files Audited → Delta vs Previous Audit
2. HTML report (if `--html` flag or Pafi requests it)
3. Cortex log entry (always) — see §3 in `AUDIT-PRO.md`
4. OpenClaw output (if `--export openclaw`)
