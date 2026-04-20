---
name: delphi-dispatch-pipeline-fix
description: Use when dispatching Delphi D3/D4 and the pipeline does not fire fully via subagent dispatch
---

# Problema

When dispatching Delphi D3/D4 research from Genie via `Agent(subagent_type="delphi-pro")`, the spawned subagent loads delphi-pro.md tools + system prompt but does NOT run the full plugin pipeline (no scout subagent fan-out, no Critic dispatch, no IL5 Source Coverage Gate enforcement, no IL6 coverage report). The subagent improvises its own execution and may silently fall back on training data when a search tool hits quota. Result: report stamped MEDIUM-HIGH confidence despite zero external verification.

# Procedura

ONLY use file-based dispatch for real Delphi D3/D4:

```bash
TASK_ID="nx-$(date +%Y%m%d)-<slug>"
# 1. Write brief to a file
BRIEF_FILE=/tmp/delphi-briefs/${TASK_ID}.md

# 2. Create task workspace (agent=delphi, complexity=high for D3/D4, budget $3)
bash ~/.nexus/scripts/nexus-task-create.sh \
  "$TASK_ID" \
  "@$BRIEF_FILE" \
  delphi \
  high \
  3.00 \
  2700

# 3. Execute (CRITICAL: only 1 positional arg = task_id; passing agent name as 2nd arg exits with "Usage:" error)
bash ~/.nexus/scripts/nexus-agent-execute.sh "$TASK_ID"
```

The file-based route uses `nexus-task-create.sh` + `nexus-agent-execute.sh` which spawns `claude --print -p` with all 36 MCP tools from agent-registry.yaml, runs through the delphi plugin pipeline (scout_0 internal enumeration, scout-web with Perplexity Sonar Pro + Brave + Exa + Tavily, scout-knowledge arXiv + OpenAlex, scout-social Reddit/HN/X, Critic Sonnet with EPR scoring, Synthesizer, IL5 Source Coverage Gate, IL6 mandatory coverage report), and enforces Iron Laws from `~/.nexus/agents/delphi/SOUL.md`.

ALTERNATIVE: slash command `/research-pro-deep <topic>` from the delphi plugin also triggers the full pipeline.

NEVER use `Agent(subagent_type="delphi-pro")` for D3/D4 — it's the wrong invocation surface for the plugin pipeline.

# Enforcement Loop

1. Before dispatching Delphi research, confirm the route: file-based (`nexus-task-create.sh` + `nexus-agent-execute.sh`) OR slash command (`/research-pro-deep`). NEVER `Agent(subagent_type="delphi-pro")` except for D1/D2 inline lookups where no scouts are needed.
2. `nexus-agent-execute.sh` signature is `<task_id>` ONLY. Passing agent name as 2nd arg returns "Usage: nexus-agent-execute.sh [--dry-run] <task_id>" and exits 1. Verify the call signature matches before running.
3. After dispatch, monitor via: `ls ~/.nexus/workspace/active/<task_id>/` + `ps -eo pid,etime,time | grep <claude pid>` + `grep <task_id> ~/.nexus/logs/agent-execute-error.log`. Key signals: scout subprocesses spawning, `output.md` created at synthesis, `Invoking quality gate` line in error log, workspace transition from `active/` to `completed/`.
4. Verify IL6 Source Coverage Report section exists at end of output report. If PARTIAL flags present, honest mode is working. If report silently lacks coverage categories, pipeline has bypassed Iron Laws — investigate.
