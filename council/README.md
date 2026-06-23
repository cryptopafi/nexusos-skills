# advisor-council — /council Skill  `v1.0.7`

`/council` runs a three-model max-reasoning council (Ollama Cloud GLM 5.2, Claude
Opus 4.8, GPT-5.5) against a brief, anonymizes and voice-normalizes all three
advisor outputs, then passes them to a runtime-native reconciler that synthesizes a
single tier-stamped verdict while preserving documented dissent. If one primary
advisor lane is unavailable after retry, the orchestrator tries fallback
advisors in deterministic order: Ollama Cloud GLM 5.2, then DeepSeek V4 Pro.
Substitutes are marked in the advisor record and the original failure is
preserved for auditability. Built against
three documented 2026 multi-model failure modes: same-family ensemble collapse,
sequential debate conformism, and reconciler self-enhancement bias. All three
mitigations are mandatory in every run.

## What `/council` Does

`/council` audits ideas, business proposals, development plans, and strategic
decisions that carry real consequence or irreversibility. Three advisors from
different model families independently review the same brief at maximum
reasoning intensity, without seeing each other's output. Their responses are
anonymized and passed to a reconciler that identifies agreement zones, split
zones, and any critical blockers before returning a final verdict tier. The
final verdict also includes Perplexity-style explainability sections: each
advisor's public position, an agreement matrix, a disagreement matrix, and a
short synthesis trace explaining how the visible advisor positions led to the
final tier.

For analytical mandates, `/council` now uses a direct-answer path. Each advisor
places its public substantive report in `direct_answer_md`; the reconciler then
synthesizes the actual answer before the committee explainability sections. This
prevents long analytical prompts from being reduced to "prompt approved/revise"
meta-verdicts.

`/council` is NOT a code auditor. For code and artifact quality scoring, use
`/audit-pro`.

## When to Use vs When Not

| Target | Use | Why |
|---|---|---|
| Code file / artifact (correctness, style review) | `/audit-pro` | Has definitive NPLF scoring |
| Multi-file architecture plan (generation + review) | `ralplan` (then `/council` if high-stake) | Plan generation + structural audit |
| Idea / business proposal / strategic decision | **`/council`** | Judgment under uncertainty |
| Investment/market/strategy analysis with required report sections | **`/council`** | Direct-answer synthesis plus advisor dissent |
| Trivial or easily reversible (single-file rename) | Direct execution, no council | Council is overkill; triage gate will refuse |

Canonical high-stake chain: `ralplan` generates plan → `/audit-pro` scores
artifact quality → `/council` judges strategic merit → TECH dispatches.

## Quick Start

```bash
/council ~/.nexus/workspace/plans/my-proposal.md
/council "Should we expand to EU in Q4 2026?" --depth quick
/council ~/path/to/big-decision.md --depth deep
```

## CLI Flags

| Flag | Default | Purpose |
|---|---|---|
| `--depth quick\|standard\|deep` | `standard` | Cost cap + advisor timeout. quick=$2/75s, standard=$6/200s, deep=$18/400s + debate round |
| `--no-debate` | False | Skip debate round even in deep mode |
| `--force` | False | Bypass triage gate (council runs even on low-stakes briefs) |
| `--min-quorum 2\|3` | 3 | 2 allows partial verdict if one advisor abstains |
| `--keep-chains` | False | Persist raw advisor reasoning chains locally (chmod 600, 7-day purge) |
| `--force-test` | False | Run AC-7 6-permutation order-bias harness (developer use only) |

Fallback advisor credentials:

- `OLLAMA_API_KEY` enables `ollama-glm-5.2-cloud`; `OLLAMA_BASE_URL` can point
  to a non-default Ollama host.
- `DEEPSEEK_API_KEY` enables `deepseek-v4-pro`; `DEEPSEEK_BASE_URL` can point
  to a non-default DeepSeek-compatible endpoint.

## Pipeline

The council runs eight sequential steps per invocation. Below is a worked
example for: `/council ~/proposals/eu-expansion.md --depth standard`

```
Step 1 — Workspace init
   council-20260519-2010-x9k2 created at ~/.nexus/workspace/council/

Step 2 — Triage (runtime-native support model)
   Brief: "Launch EU SMS marketing $50K Q4 2026..."
   Score: 72/100 (PROCEED — above threshold 40)

Step 3 — Normalize (runtime-native support model)
   <council_brief> XML written to brief.md

Step 4 — Parallel advisors (200s timeout at standard depth)
   Lane A (Ollama Cloud GLM 5.2, num_ctx=131072): PASS conf=0.82
   Lane B (Opus 4.8, thinking.effort=high): REVISE conf=0.71
   Lane C (GPT-5.5, reasoning.effort=xhigh): PASS conf=0.78

Step 5 — Anonymize (5a strip + 5b runtime voice-norm + 5c shuffle)
   reasoning_chain dropped from all disk-bound dicts
   bullets neutralized through runtime support-model voice normalization
   seed=2840193 logged in seed.json for replay
   Letters A/B/C assigned post-shuffle (not by model family)

Step 6 — Reconcile (runtime-native support model)
   tier=PASS conf=0.74
   1 agreement zone (market timing) cited Responses A+B+C
   1 split zone (EU regulatory exposure) cited Response B vs A+C

Step 7 — Debate: skipped (depth=standard; runs only at depth=deep)

Step 8 — Ledger writeback
   Local: 9 files at ~/.nexus/workspace/council/council-20260519-2010-x9k2/
   Cortex: <uuid>
   Telegram via Lis: "🏛 council-20260519-2010 PASS conf=0.74 cost=$4.82"
   Notion: skipped (not STRONG_PASS or BLOCK)

Total: $4.82 / $6.00 cap. Wall-clock 187s.
```

## Output Structure

Each invocation writes to `~/.nexus/workspace/council/<task-id>/`:

- `brief.md` — canonical normalized brief sent to all advisors
- `anonymized.json` — sanitized advisor outputs (no reasoning_chain)
- `advisor-{A,B,C}-structured.json` — per-advisor verdict, confidence, NPLF score, bullets (no chains)
- `advisor-{A,B,C}-raw.json` — ONLY present if `--keep-chains` was set, chmod 600
- `verdict.md` — reconciler's full markdown verdict with Agreement and Split sections
- `dissent.md` — Split Zones section only (standalone dissent log for review)
- `seed.json` — shuffle seed + shuffle_map for deterministic replay
- `cost.json` — full cost ledger by step
- `debate.json` — only written if `--depth deep` was used

For direct-answer mandates, `verdict.md` also includes the synthesized answer
and Perplexity-style sections: `Substantive Answer`, `Where Models Agree`,
`Where Models Disagree`, and `Unique Discoveries`.

## Privacy Contract

- Default mode: NO `reasoning_chain` is written anywhere on disk after invocation completes.
- `--keep-chains`: raw chains persist with chmod 600 per file, parent dir chmod 700, and auto-purge after 7 days (controlled by `keep_chains_retention_days` in frontmatter).
- Cortex and Notion writebacks ALWAYS strip chains regardless of `--keep-chains`.
- AC-12 test verifies default behavior: `find ~/.nexus/workspace/council -exec grep -l reasoning_chain {} \;` must return empty in a default run.
- Explainability sections are built from public advisor fields only: verdict,
  confidence, strengths, risks, blockers, `direct_answer_md`, agreement zones,
  and split zones.

## Six Tiers Explained

| Tier | Meaning | What to do |
|---|---|---|
| STRONG_PASS | All 3 advisors PASS conf>=0.85, reconciler PASS conf>=0.85, NPLF gate >=3.5 | Proceed with confidence |
| PASS | 2/3 advisors PASS, reconciler PASS, NPLF gate >=3.0 | Proceed with caveats; read agreement zones first |
| SPLIT | No 2-of-3 majority OR reconciler conf <0.65 | Human decides — read dissent.md; normative split present |
| BLOCK | Any critical_blocker flagged and reconciler agrees | Revise the proposal before proceeding |
| PARTIAL_QUORUM | 2+ advisors abstained, 1 still returned PASS | Decision rests on N=1; confidence capped at 0.75 |
| ABSTAIN | 2+ advisors failed entirely | INSUFFICIENT_QUORUM — retry or escalate to Pafi |

## Cost Expectations

| Depth | Cap | Typical | Use case |
|---|---|---|---|
| quick | $2.00 | ~$1.20 | Sanity check on an idea |
| standard | $6.00 | ~$4.50 | Business proposal review |
| deep | $18.00 | ~$14.00 | Major strategic decision + optional debate round |

Daily ceiling: $50.00 (individual runs can exceed if `--force` is passed).

Triage (Step 2, runtime-native support model) runs first on every invocation and refuses
briefs scoring below 40/100, preventing advisor cost on trivial calls.

## Dependencies and Environment

Runtime dependencies:
- Python 3.11+
- CLI tools: `codex`, `claude`, `gemini`
- Python packages: `google-generativeai` or `google-genai`; `google-api-core`

Optional overrides:
- `COUNCIL_RUNTIME=codex|claude-code` selects the support runtime explicitly.
  `.agents` and `.codex` installs intentionally default to Codex/GPT-5.5;
  `.claude` installs default to Claude Code/Opus 4.8.
- `COUNCIL_SUPPORT_PROVIDER=<provider-key>` overrides support calls only.
- `COUNCIL_WORKSPACE_DIR=<path>` overrides verdict/workspace output.
- `COUNCIL_STATE_DIR=<path>` or `COUNCIL_DAILY_SPEND_PATH=<file>` overrides
  daily spend state.
- `COUNCIL_CORTEX_URL=<url>` overrides Cortex writeback.
- `COUNCIL_VPS2_SECRETS=<file>` overrides the optional Telegram sink secret
  file.

## Design References

- Plan: `~/.nexus/workspace/plans/advisor-council-2026-05-19.md` (v0.4, NPLF 3.775, Ralph-converged)
- Procedure: `~/.nexus/procedures/PROC-COUNCIL-DESIGN-001.md`
- Cortex: research `53cb216c`, API params `21fe8280`, procedure `fbbf76ba`
- Delphi D3 (Depth-3 research) report: https://cryptopafi.github.io/nexusos-reports/delphi-council-skill-2026.html

## Limitations (v1.0)

These are known, documented constraints — not aspirational gaps. Do not work
around them silently.

- **Sequential advisor calls:** Step 4 calls the three advisors one at a time. Parallel dispatch is the v1.1 roadmap item; it would save approximately 60% of wall-clock time at standard depth.
- **Runtime support routing:** Triage, brief normalization, voice normalization, and reconciliation use the host runtime model: GPT-5.5 for Codex/.agents, Claude runtime for Claude Code. Only the three advisor/auditor lanes remain fixed multi-vendor lanes.
- **Reconciler family tradeoff:** The reconciler is runtime-native, so it can share a family with one advisor lane. Anonymization mitigates but does not eliminate this correlated-bias risk.
- **Support-model fallback remains limited:** Advisor lanes now have GLM/DeepSeek
  fallbacks, but if the host runtime support model is unreachable, triage,
  normalization, anonymization, and reconciliation can still fail. v1.1 adds a
  warm-pool fallback for support routing.
- **Western/English training bias:** All three advisor models are trained primarily on Western and English-language corpora. Confidence scores on non-Western strategic decisions should be treated with documented skepticism.
- **Notion writeback is a stub (v1.0.4):** `_write_notion` always returns `notion_mcp_unavailable`. STRONG_PASS and BLOCK verdicts still receive Telegram + Cortex + filesystem records. Full Notion MCP (Model Context Protocol) integration ships in v1.1.
