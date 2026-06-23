---
name: delphi
description: "Dispatch Delphi/NexusOS research jobs from Codex through the existing Delphi Pro plugin. Use when Pafi asks Codex to run Delphi, D1-D4 research, deep research, scout/citation-heavy research, or NexusOS research briefs."
argument-hint: <topic> [--depth auto|D1|D2|D3|D4] [--budget USD]
model: gpt-5.2-codex
version: 1.2.1
---

# /delphi — Codex Adapter for NexusOS Delphi

This skill gives Codex direct access to Delphi by wrapping the existing NexusOS/Claude Delphi implementation. It does not duplicate Delphi Pro logic.

## Decision

Use a **thin adapter**, not a rewrite:

- Delphi Pro source of truth: `~/.claude/plugins/delphi/`
- NexusOS agent identity: `~/.nexus/agents/delphi/`
- V2 wrapper/iron laws: `~/.nexus/v2/agents/delphi/`
- Codex entrypoint: `scripts/codex-delphi-dispatch.sh`

Exact in-process replication of Claude Delphi Pro is not technically correct because Delphi Pro relies on Claude Code plugin semantics, Claude CLI model routing, Agent-tool scout dispatch, and plugin-local skills/resources. Codex uses those files as specifications, then runs its own `codex` backend without Claude runtime dependencies.

The dispatcher passes Delphi's full D3/D4 tool allowlist to Claude CLI, including Agent, Skill, Cortex, Tavily, Brave, Exa, ArXiv, Wikipedia, OpenAlex, and YouTube transcript MCP tool names. Actual availability still depends on Claude CLI quota and MCP configuration.

## Usage

```bash
~/.codex/skills/delphi/scripts/codex-delphi-dispatch.sh \
  --topic "research topic" \
  --budget 0.15 \
  --backend codex
```

Optional:

```bash
--timeout 900
--model claude-sonnet-4-6
--depth D1|D2|D3|D4
--backend auto|codex|claude|python
--store-cortex
--dry-run
```

## Depth Rules

- If `--depth` is omitted, auto-classify before dispatch using Delphi Pro intake rules.
- `D1`: quick lookup, low budget, no critic.
- `D2`: standard brief, multi-source, default for normal research.
- `D3`: deep research, critic required by Delphi rules.
- `D4`: exhaustive research. In the Codex backend, an explicit Pafi-requested D4 dispatch is treated as owner-authorized and writes `d4-approved.json` plus `d4-approval-used.json` for auditability before running. Use only when Pafi explicitly asks.

## Auto-Classification

Codex mirrors Delphi Pro's Claude-side routing:

- `D1`: single factual lookup, `quick check`, `what is X`, short public-knowledge answer.
- `D2`: normal `research`, comparison, multiple perspectives, exploratory technology landscape.
- `D3`: `deep research`, strategic synthesis, competitive intelligence, trend analysis, complex/high-stakes/academic topics with complexity score ≥3.
- `D4`: explicit `D4`, `exhaustive`, `investment-grade`, `Pafi-grade`, due diligence, final/production-lock decisions. Codex dispatch auto-writes an owner approval marker for explicit D4 requests; direct low-level runner calls still require an approval artifact or flag.

The dispatcher records `depth_source: auto|explicit` in `DISPATCH.md` so downstream gates know whether depth was inferred or forced.

## Output Contract

The adapter creates a task workspace under:

```text
~/.nexus/workspace/codex-delphi/codex-delphi-YYYYMMDD-HHMMSS-PID/
```

It writes:

- `DISPATCH.md`
- `PROGRESS.md`
- `EXECUTION.log`
- `output.md`
- `credential-matrix.json` for the Codex backend
- `delphi-result.json` and `critic.json` for Codex D2/D3/D4 runs
- `d4-approved.json` and `d4-approval-used.json` for owner-authorized Codex D4 runs

If `--store-cortex` is set and Cortex is reachable, it stores `output.md` to Cortex collection `research` with `genie_visible: true`.

## Backends

- `auto`: use the Codex-native Delphi backend.
- `codex`: run Delphi through local Python/Codex code with no Claude CLI, Claude Code plugin, Anthropic Claude model, Claude agent, or Claude quota dependency.
- `claude`: legacy backend that uses the real Delphi Pro plugin through Claude CLI.
- `python`: use the local deterministic Delphi research engine only.

The Codex backend reads Delphi Pro files as specifications only and produces Delphi-compatible workspace artifacts. The Python backend is useful for low-level smoke tests but does not write the full Codex workspace contract.

## VERIFY

Run these checks after changing the adapter:

```bash
bash -n ~/.codex/skills/delphi/scripts/codex-delphi-dispatch.sh
cd ~/repos/delphi && pytest -q tests/test_codex_runner.py && pytest -q
~/.codex/skills/delphi/scripts/codex-delphi-dispatch.sh --topic "D1 smoke" --depth D1 --backend codex --dry-run
~/.codex/skills/delphi/scripts/codex-delphi-dispatch.sh --topic "D4 owner-approved smoke" --depth D4 --backend codex --timeout 60
```

Expected results:

- Syntax and pytest commands exit `0`.
- D1 dry-run workspace has `budget_usd: 0.01`.
- D4 Codex workspace has `d4-approved.json`; it should not stop at `BLOCKED_BY_D4_GATE`. It may still finish `INCOMPLETE` if the D4 quality contract fails.
- Codex backend output always includes `claude_runtime: false`.

## Safety

- Do not copy secrets.
- Do not edit Delphi plugin files.
- Do not claim exact replication unless an E2E Delphi job succeeds.
- Prefer `D1` or `D2` smoke tests before `D3/D4`.
- If Claude quota or plugin runtime fails, preserve the workspace and report the failure.

## When Blocked

If Claude CLI, quota, or Agent-tool access is unavailable, report:

- task workspace path
- exact failing command class, without secrets
- whether `DISPATCH.md`, `PROGRESS.md`, and `EXECUTION.log` were created
- recommended fallback: Codex-native research or Genie/Delphi dispatch

## Changelog

- `1.1.0` — Added Codex-native backend contract, no-Claude runtime guarantee, workspace artifact list, and verification checklist.
- `1.2.0` — Added Delphi Pro-compatible auto-classification when `--depth` is omitted and records `depth_source`.
- `1.2.1` — Explicit Pafi-requested Codex D4 dispatches now auto-write owner approval artifacts instead of stopping at the D4 gate.
