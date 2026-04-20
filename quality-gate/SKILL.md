---
name: quality-gate
description: "Run fast acceptance check on subagent output quality"
---

Run fast acceptance check on subagent output quality

# Quality Gate

## Purpose
Apply a strict PASS/FAIL gate before accepting delegated outputs.

## Instructions
1. Compare output against original task objective.
2. Validate output format against required schema/spec.
3. Check whether factual claims are verifiable.
4. Return exactly PASS or FAIL with one specific reason.
5. Recommend retry path if failed.

## Constraints
No verbose commentary.
No partial pass states.
Fail when evidence is insufficient.
