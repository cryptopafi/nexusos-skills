---
name: code-feature-template
description: "Step-by-step feature implementation template."
---

Step-by-step feature implementation template. Forces one step at a time to avoid scope creep and high token cost.

# Code Feature Template

Use this for any new feature. Always implement ONE step at a time — wait for confirmation before continuing.

```
Feature: [clear description]
Current step: [1/N — describe only this step]
Acceptance criteria:
- [criterion 1]
- [criterion 2]
- [criterion 3]
Allowed scope: [list exact files/folders]
Rules: strict typing, no new deps without approval, no lateral refactor.
Output:
1) Patch for this step only
2) How to test locally (max 5 commands)
3) What step 2 would be (d
