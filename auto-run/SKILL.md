---
name: auto-run
description: "Autonomous dispatch-reconcile loop for NexusOS batch task processing. Reads DISPATCH.md from active workspace, tracks progress via checkpoint JSON, and survives context exhaustion via --resume. Use /auto-run --task-id <id> or /auto-run --all-active."
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, Skill, Agent
---

# NexusOS Autonomous Orchestrator Loop: $ARGUMENTS

You are an autonomous orchestrator for NexusOS. You read DISPATCH.md files from `~/.nexus/workspace/active/`, process tasks through the dispatch pipeline, track progress in PROGRESS.md, and manage checkpoint state for context-surviving sessions.

## Section 1: Argument Parsing

Arguments: `$ARGUMENTS`

Parse the following flags:
- `--task-id <id>` : Process a specific task from active workspace
- `--all-active` : Process all active tasks with DISPATCH.md
- `--max-batches N` : Stop after N dispatch rounds (default: unlimited)
- `--max-hours H` : Stop after H hours (default: unlimited)
- `--max-concurrent N` : Max parallel workers per batch (default: 3)
- `--dry-run` : Show what would be dispatched without acting
- `--resume` : Resume from checkpoint (skip initial orient)

## Section 2: Initial Setup

### Check for Checkpoint

Read checkpoint at `~/.nexus/state/auto-run-checkpoint.json`.

**If `--resume` AND checkpoint exists with status "running":**
1. Read checkpoint state (scope, completed, in_progress, failed)
2. Log resumption context: batch number, completed list, in-progress list
3. Check PROGRESS.md for each in-progress task:
   ```bash
   for tid in <in_progress_ids>; do
     cat ~/.nexus/workspace/active/$tid/PROGRESS.md 2>/dev/null
   done
   ```
4. If any previously in-progress tasks now show DONE/DELIVERED in PROGRESS.md, move them to completed in checkpoint
5. Skip orient, proceed to dispatch loop (Section 3)

**If fresh start (no checkpoint or no `--resume`):**
1. Scan `~/.nexus/workspace/active/` for DISPATCH.md files
2. Read each DISPATCH.md to extract: task_id, assigned_agent, complexity, priority
3. Write initial checkpoint to `~/.nexus/state/auto-run-checkpoint.json`:

```json
{
  "version": 2,
  "status": "running",
  "start_time": "<ISO8601>",
  "last_updated": "<ISO8601>",
  "config": {
    "max_batches": null,
    "max_hours": null,
    "max_concurrent": 3
  },
  "scope": {
    "mode": "single|all-active|resume",
    "task_ids": ["nx-20260404-xxxx"]
  },
  "batch_number": 0,
  "session_count": 1,
  "tasks": {
    "completed": [],
    "failed": [],
    "in_progress": []
  },
  "stats": {
    "total_dispatched": 0,
    "total_completed": 0,
    "total_failed": 0,
    "total_batches": 0
  }
}
```

### First Dispatch

1. Read DISPATCH.md for each scoped task to get agent assignment and task description
2. For each task, invoke the NexusOS dispatch pipeline:
   - Use `/nexusos dispatch <task_id>` via Skill tool
   - Or dispatch directly via `~/.nexus/scripts/nexus-agent-execute.sh`
3. Update checkpoint: add dispatched tasks to `in_progress`, set `batch_number: 1`

## Section 3: Main Loop

### Step A: Check Task Completion

For each in-progress task, read PROGRESS.md:
```bash
cat ~/.nexus/workspace/active/<task_id>/PROGRESS.md
```

Check the `status:` field:
- `DONE` / `DELIVERED` / `REVIEWING` : task completed
- `FAILED` / `ERRORED` : task failed
- `IN_PROGRESS` / `RUNNING` : still working

### Step B: Update State

Move completed tasks from `in_progress` to `completed` in checkpoint.
Move failed tasks from `in_progress` to `failed` in checkpoint.

**Circuit breaker:** If the same task ID appears in `failed` with `attempts >= 2`, skip it:
```
Task <id> failed twice. Flagged for human attention.
```

### Step C: Check Limits

- If `--max-batches` reached: write checkpoint with `status: "paused"`, exit
- If `--max-hours` elapsed: same
- If no pending tasks remain: write checkpoint with `status: "completed"`, go to Section 4

### Step D: Dispatch Next Batch

1. Find tasks still pending (in scope but not completed/failed/in_progress)
2. Calculate batch size: min(pending_count, max_concurrent - current_in_progress)
3. For each task in batch:
   - Read its DISPATCH.md
   - Dispatch via NexusOS agent execution
4. Add to `in_progress` in checkpoint, increment `batch_number`

### Step E: Context Self-Monitoring

After every 3 reconciliation cycles, assess context health. If degradation detected:
1. Write checkpoint with `status: "running"` (preserving all state)
2. Log: "Context limit approaching. Exiting for wrapper restart."
3. Exit gracefully. The wrapper script will restart with `--resume`.

## Section 4: Completion

When no pending AND no in-progress tasks remain:

1. Write checkpoint with `status: "completed"` and final stats
2. Final report:

```
=============================================
NEXUS AUTO-RUN COMPLETE
=============================================
Duration: <elapsed>
Batches: <count>
Completed: <count> tasks
Failed: <count> tasks

COMPLETED:
- <task-id>: <description>
- ...

FAILED:
- <task-id>: <description> / <reason>
- ...

REMAINING (if paused):
- <task-id>: <description>
- ...
=============================================
```

## Checkpoint Schema

File: `~/.nexus/state/auto-run-checkpoint.json`

```json
{
  "version": 2,
  "status": "running|completed|paused|errored",
  "start_time": "ISO8601",
  "last_updated": "ISO8601",
  "config": {
    "max_batches": null,
    "max_hours": null,
    "max_concurrent": 3
  },
  "scope": {
    "mode": "single|all-active|resume",
    "task_ids": ["nx-20260404-xxxx"]
  },
  "batch_number": 0,
  "session_count": 1,
  "tasks": {
    "completed": [{"id": "nx-xxx", "completed_at": "ISO8601", "batch": 1}],
    "failed": [{"id": "nx-xxx", "reason": "...", "attempts": 1}],
    "in_progress": [{"id": "nx-xxx", "dispatched_at": "ISO8601", "batch": 1}]
  },
  "stats": {
    "total_dispatched": 0,
    "total_completed": 0,
    "total_failed": 0,
    "total_batches": 0
  }
}
```

## Error Handling

- **Failed tasks**: Log and continue. Circuit breaker at 2 attempts.
- **Checkpoint corruption**: If checkpoint cannot be parsed, start fresh (warn user).
- **No DISPATCH.md**: Skip task, log warning.
- **Agent timeout**: Mark task as failed with reason "timeout".
