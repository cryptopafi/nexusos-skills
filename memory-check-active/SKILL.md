---
name: memory-check-active
description: memory check for zombie processes
---

<task>macOS System Performance Audit + Remediation</task>

<context>
Platform: macOS 26.x (Sequoia), Apple Silicon ARM64
RAM: 16 GB | CPU: 10-core | Primary machine (MacM4)
Running: NexusOS agents, LaunchAgents, background daemons
Goal: Identify and eliminate everything slowing down the system.
</context>

<instructions>
Execute a full system performance audit in 6 ordered phases.
Think step-by-step (ReAct). After each phase, list findings before acting.

## Phase 1 — Zombie & Defunct Process Scan
Run: ps aux | awk '$8 == "Z"'
For each zombie: identify parent PID → assess if parent is killable → kill parent if safe.
Classification rule: system parent (launchd, kernel_task) → log only. User parent → kill.

## Phase 2 — Top CPU Consumers (last 5 minutes)
Run: ps aux --sort=-%cpu | head -30
For each process > 5% CPU:
  - Identify: what is it? (system / NexusOS / user app / unknown)
  - Classify: ESSENTIAL | USEFUL | ZOMBIE-JOB | UNKNOWN
  - Action: PRESERVE | RESTART | KILL
NexusOS processes (nexus, echelon, iris, genie, lis, codex) → always PRESERVE.
Apple system processes (kernel_task, WindowServer, mds) → always PRESERVE.

## Phase 3 — Memory Pressure Analysis
Run: vm_stat && top -l 1 -n 0 | grep -E "PhysMem|Swap"
Flag: swap usage > 1GB = HIGH PRESSURE
List top 10 RAM consumers: ps aux --sort=-%mem | head -10
Classify each as ESSENTIAL / KILLABLE.

## Phase 4 — LaunchAgents & LaunchDaemons Audit
Scan:
  - ~/Library/LaunchAgents/ (user agents)
  - /Library/LaunchAgents/ (system-wide user agents)
  - /Library/LaunchDaemons/ (system daemons)

For each .plist:
  1. Read Label and ProgramArguments
  2. Check if loaded: launchctl list | grep <label>
  3. Classify:
     - SYSTEM (com.apple.*) → PRESERVE
     - NEXUSOS (com.nexus.*, com.genie.*, com.echelon.*, com.claude.*) → PRESERVE
     - KNOWN TOOL (com.homebrew.*, com.dropbox.*, etc.) → REVIEW (needed?)
     - UNKNOWN / ORPHANED → UNLOAD candidate
  4. For UNLOAD candidates: launchctl unload -w <path>

## Phase 5 — Orphaned Network Listeners
Run: lsof -iTCP -sTCP:LISTEN -n -P | grep -v "COMMAND"
For each listener: identify process → classify → kill if unknown/unused.
Flag: anything listening on unexpected ports.

## Phase 6 — Duplicate / Runaway Jobs
Check for:
  - Multiple instances of same process: ps aux | awk '{print $11}' | sort | uniq -c | sort -rn | head -20
  - Processes running > 24h: ps aux | awk '$10 ~ /[0-9]+-/ {print $0}'
  - For duplicates of user processes: kill all but one

## Output Format
Produce a structured report:

=== SYSTEM AUDIT REPORT — {date} ===

🧟 ZOMBIES: {count} found, {count} killed
🔥 HIGH CPU: {list with action taken}
🧠 MEMORY PRESSURE: {level} | Swap: {size}
⚙️ LAUNCHAGENTS: {count} audited | {count} unloaded | {list}
🌐 NETWORK: {count} listeners | {count} flagged
♾️ DUPLICATES: {list with action}

ACTIONS TAKEN:

Killed: {list}
Unloaded: {list}
Preserved: {count} (system + NexusOS)
RECOMMENDATIONS:

{any follow-up actions needed}

## Safety Rules (CRITIC check before each action)
❌ NEVER kill: kernel_task, launchd, WindowServer, mds, coreaudiod, com.apple.*
❌ NEVER unload: Apple system agents, NexusOS agents
✅ ALWAYS log action before executing
✅ If unsure → classify as REVIEW, log, skip kill
</instructions>

<output>Execute all 6 phases autonomously. Deliver the full report at the end.</output>