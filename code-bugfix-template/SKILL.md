---
name: code-bugfix-template
description: "Generate a minimal, cost-efficient bugfix prompt for Tech agent."
---

Generate a minimal, cost-efficient bugfix prompt for Tech agent. Prevents over-engineering and context bloat.

# Code Bugfix Template

Use this template when asked to fix a bug. Fill in the placeholders and execute.

```
Stack: [Node 20/TS | Python 3.11 | Go 1.22 | other]
File(s): [exact paths]
Error: [exact message + 20-60 relevant log lines]
Task: Fix root cause only. No API changes. No extra refactor.
Constraints: No new dependencies.
Output:
1) Unified patch
2) Root cause in 3 bullets
3) Regression test
4) Test command: [npm test / pytest -k / go test]

If info is not needed for the fix, do not proce
