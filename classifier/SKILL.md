---
name: classifier
description: "Route tasks to haiku/sonnet/opus based on size and complexity"
---

Route tasks to haiku/sonnet/opus based on size and complexity

# Classifier

## Purpose
Select the best model tier for cost-aware high-quality execution.

## Instructions
1. Estimate output size bucket: `<1K`, `1K-5K`, `>5K`.
2. Classify complexity: lookup/format, analysis/code, architecture/audit.
3. Apply routing:
   - simple + <1K -> haiku
   - analysis/code + 1K-5K -> sonnet
   - architecture/audit or >5K -> opus
4. Return strict format: `MODEL: X | REASON: Y`.

## Constraints
Reason must be <=10 words.
No extra prose.
Prefer higher tier when risk is am
