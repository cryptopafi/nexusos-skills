---
name: multi-review
version: "1.0.0"
description: "Parallel peer review gate for TECH sub-agent deliveries. Spawns 3-5 specialized reviewers (security, correctness, integration) after BUILDER/FIXER completes. Gates on majority PASS. Blocking CRITICAL from any reviewer stops merge. Invoked with /multi-review or auto-triggered by TECH verify-after-write pipeline (IL-11/12/13 augmentation). Works standalone on any file/directory (degrades gracefully without NexusOS workspace)."
allowed-tools: Read, Bash, Glob, Grep, Agent, AskUserQuestion
---

# Multi-Review: Parallel Peer Review Gate for NexusOS

You are orchestrating a peer review of a TECH sub-agent delivery using multiple specialized reviewers in parallel.

## When to Invoke

- After BUILDER completes a delivery (>50 lines new code)
- After FIXER applies audit findings (FORGE-AUDIT fixes)
- After INTEGRATOR wires 2+ components
- When GENIE or TECH explicitly calls `/multi-review`
- As augmentation to IL-11 (grep-verify), IL-12 (runtime test), IL-13 (consumer test)

## Arguments

- No args: reviews the most recent delivery in `~/.nexus/workspace/active/` (latest by mtime)
- `<task_id>`: reviews specific delivery at `~/.nexus/workspace/active/{task_id}/`
- `<file_path>`: reviews a specific file or directory
- `--light`: 3 reviewers only (security, correctness, integration)
- `--full`: 5 reviewers (adds style, performance)

## Workflow

### Step 1: Identify Target

Determine what to review:
1. If task_id provided: read `~/.nexus/workspace/active/{task_id}/PROGRESS.md` for output files
2. If file path provided: use directly
3. If no args: find latest modified workspace in `~/.nexus/workspace/active/`
4. Fallback: `git diff HEAD~1 --name-only` for recent changes

List all target files with line counts.

### Step 2: Spawn Reviewers

Launch 3-5 parallel review agents using the Agent tool. Each reviewer operates independently.

**Core reviewers (always, --light or default):**

| Reviewer | Focus | Check For |
|----------|-------|-----------|
| **security-reviewer** | Injection, auth bypass, secrets exposure, unsafe eval, OWASP top 10 | Command injection in bash, hardcoded secrets, path traversal, unvalidated input |
| **correctness-reviewer** | Logic errors, edge cases, off-by-one, unreachable code, wrong conditions | Does the code do what DISPATCH.md says? Are acceptance criteria met? |
| **integration-reviewer** | Does this break existing NexusOS components? Import paths, state files, hook wiring | Check consumers: who calls this? What changes for them? |

**Extended reviewers (--full only):**

| Reviewer | Focus |
|----------|-------|
| **style-reviewer** | NexusOS conventions, naming, file organization, FORGE compliance |
| **performance-reviewer** | Unnecessary loops, blocking I/O, large file reads, O(n^2) patterns |

Each reviewer agent receives:
- The target file contents
- The DISPATCH.md (what was requested) -- if available
- The PROGRESS.md (what was claimed done) -- if available
- Instruction: "Produce findings as: ID, SEVERITY (CRITICAL/HIGH/MEDIUM/LOW), SUMMARY, FIX. Return PASS or FAIL verdict."

**Standalone mode (no DISPATCH.md/PROGRESS.md):** When context files are absent, reviewers operate in file-only mode. Skip acceptance-criteria validation (correctness-reviewer checks internal logic only). Security and integration reviewers function normally.

**Timeout:** Each reviewer agent has a 120-second soft limit. If a reviewer has not returned after 120s, mark it SKIPPED and proceed with available verdicts. Use the Agent tool's natural completion; do not add artificial waits.

### Step 3: Collect Verdicts

Wait for all reviewers to complete. Build verdict table:

```
| Reviewer | Verdict | Findings |
|----------|---------|----------|
| security | PASS | 0 |
| correctness | PASS | 1 (LOW) |
| integration | FAIL | 1 (HIGH) |
```

### Step 4: Gate Decision

**PASS conditions (ALL must be true):**
- Majority of reviewers return PASS (2/3 or 3/5)
- Zero CRITICAL findings from ANY reviewer
- Zero HIGH findings from security-reviewer specifically

**FAIL conditions (ANY triggers FAIL):**
- Any CRITICAL finding from any reviewer
- Majority FAIL (2/3 or 3/5 return FAIL)
- Any HIGH from security-reviewer

**CONDITIONAL:**
- Majority PASS but HIGH findings exist (non-security)

### Step 5: Report

Output the review summary:

```
## Multi-Review: {task_id or file}

| Reviewer | Verdict | Findings |
|----------|---------|----------|
| ... | ... | ... |

### Gate: PASS / CONDITIONAL / FAIL

### Findings (if any)
{numbered list of all findings across all reviewers, sorted by severity}

### Recommendation
{MERGE / FIX-THEN-MERGE / BLOCK}
```

### Step 6: Post-Review Actions

- **PASS/MERGE**: No action needed. TECH proceeds with delivery.
- **CONDITIONAL/FIX-THEN-MERGE**: List specific fixes. TECH applies fixes, then re-runs `/multi-review --light`.
- **FAIL/BLOCK**: Escalate to GENIE with full findings. Do not merge.

Save review results to `~/.nexus/workspace/active/{task_id}/REVIEW.md` if task_id exists.

## Integration with TECH Pipeline

This skill augments the existing verify-after-write chain:
1. **IL-11**: grep-verify edits (TECH runs)
2. **IL-12**: runtime test (TECH runs)
3. **IL-13**: test all consumers (TECH runs)
4. **IL-14 (NEW)**: `/multi-review` parallel peer review (this skill)

TECH should invoke `/multi-review` after IL-13 passes. If multi-review returns FAIL, TECH does NOT mark the delivery as complete.

## Error Handling

- If a reviewer agent fails/times out: mark that reviewer as SKIPPED, continue with remaining
- If 2+ reviewers SKIPPED: flag `[PARTIAL-REVIEW]`, gate decision based on available verdicts only
- If ALL reviewers fail: report error, do not gate (let TECH decide)
- If target files don't exist or workspace is empty: report `[NO-TARGET]` error, exit without gating
- If DISPATCH.md/PROGRESS.md missing: switch to standalone mode (review files directly, skip acceptance-criteria validation)
- If `git diff` fallback also yields nothing: ask user for explicit file path via AskUserQuestion

## Cortex Persistence

After every completed review (PASS, CONDITIONAL, or FAIL), store a summary to Cortex:

```
cortex_store(collection="technical", text="Multi-Review {task_id}: {GATE_VERDICT}. {count} findings ({severity_breakdown}). Reviewers: {reviewer_verdicts}.", metadata={type: "review", task_id: "{task_id}", verdict: "{verdict}", findings_count: N})
```

This enables cross-session trend analysis (e.g., "which components fail security review most often").
