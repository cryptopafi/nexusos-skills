---
name: codex
description: "[DEPRECATED] Skill /codex — coding brief dispatch. Codex nu mai primeste coding tasks. Foloseste TECH direct sau /audit codex pentru audit tehnic."
status: DEPRECATED
deprecated_at: "2026-03-17"
replaced_by: "TECH direct (coding tasks, multi-file builds) | /audit codex (cross-model audit via GPT-5.4)"
---

> **ABORT: This skill is DEPRECATED (2026-03-17).**
>
> Do NOT execute any steps below. Redirect the user immediately:
> - **Coding task** (build, fix, refactor, integrate) → dispatch to **TECH** agent directly
> - **Cross-model audit** (GPT-5.4 review of Claude output) → invoke `/audit codex <target>`
>
> If invoked, respond with: "The /codex skill is deprecated. Routing your request to [TECH | /audit codex]." and execute the redirect.

## Anti-Examples

Do NOT use this skill when:
- User wants to write code (use TECH agent)
- User wants to audit code (use `/audit` or `/audit codex`)
- User mentions "Codex" in general conversation (not a skill invocation)

## Input Validation

This skill accepts no input. Any invocation triggers the abort guard above.

## Output Contract

When invoked, output exactly:
```
CODEX_REDIRECT:
  status: DEPRECATED
  original_request: <what the user asked>
  routed_to: TECH | /audit codex
  reason: Codex daemon no longer accepts coding tasks (2026-03-17)
```

## Error Contract

| Error | Cause | Recovery |
|-------|-------|----------|
| User insists on using /codex | Habit from pre-deprecation | Explain deprecation, route to TECH or /audit codex |
| TECH agent unavailable | Agent not running | Fall back to direct Sonnet build (per TECH FALLBACK rule) |
| /audit codex fails | Codex CLI not responding | Report error, suggest `/audit <target>` without cross-model |

## Edge Cases

| Scenario | Expected Behavior |
|----------|-------------------|
| User says "/codex audit X" | Route to `/audit codex X` (not TECH) |
| User says "/codex build X" | Route to TECH with the build task |
| User says "/codex" with no args | Show deprecation notice and routing options |
| Script or automation calls /codex | Return DEPRECATED status in structured format |

## Historical Reference

This skill previously dispatched coding briefs to the Codex daemon via `~/.codex/genie-to-codex.md`. The brief format (v2.1) used Goal/Context/Steps/Output/Success Criteria/Constraints/Safety sections. Model routing used gpt-5.1 through gpt-5.4 tiers.

The Codex daemon has been replaced by the TECH dev team (BUILDER/FIXER/INTEGRATOR/PIPELINER sub-agents) which provides faster turnaround, integrated audit loops, and native Claude Code tool access.
