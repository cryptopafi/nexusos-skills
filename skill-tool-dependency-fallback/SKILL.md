---
name: skill-tool-dependency-fallback
description: Use when a skill's required tools are missing — provides graceful fallback strategy for any skill
---

# Problema

The HARD rule 'USE SKILLS NOT MANUAL: Skill exists → Skill tool. Never manually run underlying scripts' gets violated when the skill's underlying tools (Python, Bash, WebSearch, openpyxl, pptxgenjs) are directly accessible and feel faster. Example violation: user asks for a financial audit 'using financial skills or plugins from library', I reference anthropic-skills:xlsx and the audit skill as available options, then build the audit from scratch using raw openpyxl + inline Python instead of invoking Skill(skill="anthropic-skills:xlsx", ...). The findings are still valid, but the delivery path skipped the skills. User catches this during handoff and asks 'did you use any financial skill?'.

# Procedura

1. Before executing any task, check the skill registry (system-reminder lists available skills). If any skill matches the task description, route through Skill tool FIRST.
2. For data files (xlsx, docx, pptx, pdf): ALWAYS use anthropic-skills:xlsx / docx / pptx / pdf via Skill tool, even if you could use the underlying library directly.
3. For audits: use the audit skill with the correct audit type (code, procedure, best-practices, config, etc.) — it returns NPLF scoring which beats ad-hoc Python.
4. Only fall back to direct tools (Python, Bash, Write) when: (a) no skill matches, (b) the skill is confirmed broken/unreachable, (c) the task is too simple for a skill (<3 tool calls).
5. If violating this rule by accident, acknowledge it honestly when caught — never defend the manual path.

# Enforcement Loop

- Gate: before any multi-step execution, pattern-match task description against skill names in system-reminder
- Rollback trigger: if user asks 'did you use X skill?' and the answer is no — acknowledge, save the lesson, offer to re-run via the skill
- Verification cadence: at end of every non-trivial task, self-check: 'did I use the right skill for this, or did I go manual?'
- Failure mode: raw-tools-are-faster rationalization. Skills provide structure, scoring, and consistency that raw tools don't
