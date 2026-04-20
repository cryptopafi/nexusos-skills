---
name: code-review-template
description: "Focused code review template — bugs and regressions only, no style noise."
---

Focused code review template — bugs and regressions only, no style noise. Cost-efficient.

# Code Review Template

Use for reviewing code changes. Focus only on what matters — skip style opinions.

```
Review scope: [file(s) or diff]
Review for:
1) Real bugs (logic errors, null refs, race conditions)
2) Behavioral regressions vs existing functionality
3) Missing critical tests

Format: findings ordered by severity (CRITICAL / HIGH / MEDIUM)
Each finding: file:line — description — suggested fix

Do NOT comment on:
- Code style or formatting
- Naming conventions (unless clearly misleadi
