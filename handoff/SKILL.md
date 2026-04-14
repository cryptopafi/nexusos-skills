---
name: handoff
description: "Complete 8-step session handoff: scan for unsaved Cortex skills, create session summary file, update task files, compact MEMORY.md, check background agents, verify active modes, git sync, and deliver final report. Use this whenever ending a session, switching contexts, or the user says 'handoff', '/handoff', 'save session', 'wrap up everything', 'session end'. This is the COMPREHENSIVE session-end procedure with zero information loss. For a quick lightweight summary, use session-summary instead."
disable-model-invocation: true
argument-hint: [optional notes about what to prioritize]
---

# /handoff — Session Handoff & Memory Optimization

> **NOTE**: This is the SESSION handoff command (save state, compact memory, prepare for next session).
> This is NOT the WISH Step H "Hand-off" execution procedure (flux selection, Codex delegation).
> For WISH Step H, see: `~/.nexus/procedures/WISH-HANDOFF.md`

You are performing a complete session handoff. This ensures ZERO information loss between sessions.
Execute ALL steps below in order. Do NOT skip any step. Report progress as you go.

Additional notes from user: $ARGUMENTS

---

## Anti-Examples

Do NOT invoke this skill when:
- The user asks for a **quick summary** of what was done — use `session-summary` instead
- The user wants to **hand off a Codex task** (WISH Step H) — see `~/.nexus/procedures/WISH-HANDOFF.md`
- The user asks to **save a single file or skill** — use Cortex store directly
- The user wants to **check agent status only** — use task status tools directly
- The session just started and nothing has been done yet — handoff with no session content creates noise

---

## Error Contract

| Error | Cause | Recovery |
|-------|-------|----------|
| Cortex HTTP 422 | FORGE format missing required sections or metadata fields | Add `# Problema`, `# Procedura`, `# Enforcement Loop`; set `has_enforcement_loop: true` (boolean), `forge_version: "2.0"` |
| Cortex unreachable | Network/service down | Save to `memory/pending-cortex-saves.md`; continue handoff |
| Notion API 404 on create | Wrong `database_id` used | Read DB ID from `~/.nexus/config/notion.json` → `team_dashboard_db_id`; do NOT use `data_source_id` |
| Notion API rate limit / 5xx | Transient error | Exponential backoff: 1s→2s→4s→8s, max 4 retries; on final failure queue to `~/.nexus/pending-dashboard-entries.json` |
| Git push rejected | Diverged remote | Report error with exact message; do NOT force-push; continue to Step 8 |
| Session file write conflict | Concurrent write (two Claude sessions running) | Acquire lock per **Concurrent Write Guard** below before writing |
| Task file missing | First run for this user | Create `memory/tasks/{user}-tasks.md` with empty scaffold |

---

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| Session file for today already exists | APPEND new content — do not overwrite |
| MEMORY.md is already under 180 lines | Skip compaction, note "Already compact" in report |
| No new Cortex skills to save | Skip Step 1 saves, announce "Nothing new to save" |
| No new tools/skills/procedures created | Skip Step 1.5 Dashboard Update entirely |
| Active mode file absent | Treat as "no active mode"; do not create the file |
| Background agents list is empty | Report "No background agents running" |
| Two Claude sessions writing simultaneously | Use lock file guard (see Concurrent Write Guard) |
| Cortex save succeeds but returns no ID | Log title + timestamp as identifier in session summary |
| `_active-user.md` absent | Default to Pafi; log warning in session summary |
| $ARGUMENTS is empty | Execute all steps with default priorities |

---

## Concurrent Write Guard

Before any file write in Steps 2 and 3, acquire a lock to prevent corruption from concurrent sessions:

```bash
LOCKFILE="/tmp/nexus-handoff-$(basename $TARGET_FILE).lock"
# Acquire lock (fail after 10s)
if ! (set -o noclobber; echo $$ > "$LOCKFILE") 2>/dev/null; then
  echo "[WARN] Lock held by PID $(cat $LOCKFILE) — waiting up to 10s"
  for i in $(seq 1 10); do
    sleep 1
    (set -o noclobber; echo $$ > "$LOCKFILE") 2>/dev/null && break
    [ $i -eq 10 ] && echo "[ERROR] Could not acquire lock for $TARGET_FILE — skipping write" && exit 1
  done
fi
# ... perform write ...
rm -f "$LOCKFILE"
```

Apply this pattern before writing `memory/sessions/session-*.md` and `memory/tasks/{user}-tasks.md`.

---

## Config References

All service coordinates MUST be read from config files — never hardcoded:

- **Cortex base URL**: read from `~/.nexus/config/cortex.json` → key `cortex_url`
  - Example: `CORTEX_URL=$(jq -r '.cortex_url' ~/.nexus/config/cortex.json)`
- **Notion Team Dashboard DB ID** (for page creation): read from `~/.nexus/config/notion.json` → key `team_dashboard_db_id`
- **Notion data_source_id** (read-only queries only): read from `~/.nexus/config/notion.json` → key `team_dashboard_data_source_id`

If a config file is missing or the key is absent, report `[CONFIG ERROR: missing {key} in {file}]` and skip the affected step rather than using a fallback hardcoded value.

---

## Step 1: Scan for Unsaved Skills (MEM-H-002)

Review everything done THIS session. For each fix, discovery, or procedure created:
- Check if it was already saved to Cortex
- If NOT saved → save immediately via `curl -s -X POST $(jq -r '.cortex_url' ~/.nexus/config/cortex.json)/api/store`
- Announce each: `[Skill #N saved: "title"]`
- If Cortex is unreachable → save to `memory/pending-cortex-saves.md` for next session

**FORGE FORMAT (MANDATORY for `procedures` collection — IL-18, FORGEBUILD §3):**
When saving to `procedures` collection, text MUST contain `# Problema`, `# Procedura`, `# Enforcement Loop` sections. Metadata MUST include:
```json
{"rule_id": "PROC-XXX-NNN", "has_enforcement_loop": true, "forge_version": "2.0"}
```
`has_enforcement_loop` must be boolean `true` (not string). `forge_version` any non-empty string (current: "2.0"). Sections are case-insensitive. Without these, Cortex returns HTTP 422.
Emergency bypass: `"forge_bypass": true, "forge_bypass_reason": "<reason>"` in metadata (logged server-side).

**Collection mapping:**
- Bug fixes, procedures, workflows → `procedures` (FORGE format required)
- Research findings, intelligence → `intelligence`
- Technical skills, findings → `technical`
- Business decisions → `business`
- Course procedures → `training_procedures`

## Step 1.5: Dashboard Update (Shared Workspace)

For each new skill, procedure, tool, or agent created or significantly updated this session:
1. Detect current user from `memory/users/_active-user.md`
2. Read Notion DB IDs from `~/.nexus/config/notion.json` (keys: `team_dashboard_db_id`, `team_dashboard_data_source_id`)
3. Create or update entry in Team Dashboard Notion DB via Notion MCP using `team_dashboard_db_id` for page creation:
   - Set Owner to current user
   - Set Status to Ready (if completed) or Building (if in progress)
   - Set UnreadByPafi = true if current user is Leo
   - Set UnreadByLeo = true if current user is Pafi
   - Fill Description, Invocation, Parent Project fields
4. For existing dashboard entries that were updated this session: update Status, re-set the other user's unread checkbox
5. Use exponential backoff on Notion API calls (1s→2s→4s→8s, max 4 retries) per HARD rule
6. If Notion unreachable: queue entries to `~/.nexus/pending-dashboard-entries.json` for flush on next session start
7. Announce: `[Dashboard #N updated: "title" for {other_user}]`

**Skip if**: No new tools/skills/procedures were created this session.

## Step 2: Create Session Summary

Acquire lock (see Concurrent Write Guard) for the session file before writing.
Write a structured session file to `memory/sessions/session-{YYYY-MM-DD}-{machine}.md`.
If a file for today already exists, APPEND to it (don't overwrite).

**Required sections:**
```markdown
# Session {YYYY-MM-DD} — {Machine} ({User})

## Major Accomplishments
- [numbered list of everything completed this session]

## Key Decisions Made
- [any business or architectural decisions]

## Files Created/Modified
- [file paths with brief description of changes]

## Notion Changes
- [DB IDs, page IDs, what was created/updated]
- [include property schemas for new DBs]

## Cortex Saves
- [list of Cortex IDs saved this session]

## Business Context Updates
- [any corrections to business info, user preferences, etc.]

## Background Agents
- [status of any running agents with task IDs]
- [what they're doing and expected completion]

## Pending Tasks
- [unfinished work with priority and context]
- [include enough detail for next session to continue without asking user]
```

## Step 3: Update Task Files

Acquire lock (see Concurrent Write Guard) for the task file before writing.
Read `memory/tasks/{user}-tasks.md`. Update it:
- Mark completed tasks with date
- Add any new pending tasks discovered this session
- For each pending task, include:
  - What needs to be done
  - Why it's pending (blocked? user said later? low priority?)
  - Any IDs, URLs, or context needed to resume

## Step 4: Compact MEMORY.md

Read `memory/MEMORY.md`. Check line count.
- If over 180 lines → move detailed session content into topic files
- Keep MEMORY.md as a concise INDEX (pointers to topic files)
- Update "Latest Session" section with today's summary (2-3 lines max)
- Ensure all topic file pointers are correct
- NEVER delete reflex sections (they're permanent)

**What stays in MEMORY.md:** Identity, reflexes, active projects list, topic index, latest session pointer
**What moves out:** Detailed session logs, conversation transcripts, long lists

## Step 5: Check Background Agents & Tasks

Run: Check for any running background tasks or agents.
- For each running agent: report status, save task ID to session summary
- For each completed agent not yet reported: summarize results
- Note any agents that need follow-up in next session

## Step 6: Check Active Mode Persistence

Read `~/.claude/active-mode.md`. If a mode is active (PRECISION or TRAINING):
- Confirm it's written to disk (will auto-restore next session)
- Note the active mode in session summary

## Step 7: Git Sync

Run the following sequence:
```bash
cd ~/.claude/projects/-Users-pafi && git add -A && git commit -m "Handoff sync from $(hostname -s) at $(date '+%Y-%m-%d %H:%M:%S')" && git push origin main
```
If sync fails → report error but continue with report.

## Step 8: Final Report

Present a clean summary to the user:

```
--- HANDOFF COMPLETE ---

Skills saved: N (list titles)
Session file: memory/sessions/session-{date}-{machine}.md
Tasks pending: N (list briefly)
Background agents: N running (list IDs)
Memory compacted: Yes/No (X lines → Y lines)
Git sync: Success/Failed
Active mode: None/PRECISION/TRAINING

Next session will auto-load:
- Session summary with full context
- All pending tasks with priorities
- Background agent IDs to check
- Active mode (if any)

Ready for new session or continuation.
```

---

## Important Rules

- NEVER ask the user questions during handoff — just execute
- NEVER skip Cortex saves — this is the #1 cause of lost knowledge
- NEVER hardcode Cortex URLs or Notion DB IDs — always read from config files
- If MEMORY.md is already compact, don't force changes
- If there's nothing new to save, say so and skip that step
- Total handoff should take <60 seconds
- This command can be run multiple times safely (idempotent)