---
name: genie-codex-handoff
description: "Build self-contained Genie->Codex execution briefs"
---

Build self-contained Genie->Codex execution briefs

# Genie Codex Handoff

## Purpose
Standardizeaza handoff-urile Genie -> Codex astfel incat executia sa porneasca fara clarificari.

## Instructions
1. Alege modelul dupa volum:
   - > 500 linii: `gpt-5.3-codex` + `xhigh`.
   - 100-500 linii: `gpt-5.2-codex` + `high`.
   - < 100 linii: `gpt-5.1-codex-mini` + `medium`.
   - ingestion: `gpt-5.2-codex` + `high`.
2. Scrie brief-ul self-contained cu: `Date`, `TaskID`, `Priority`, `Title`, `Model Setting`, `Context`, `Task`, `Output Requirements`, `Del
