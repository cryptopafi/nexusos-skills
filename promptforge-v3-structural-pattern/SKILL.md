---
name: promptforge-v3-structural-pattern
description: Use when applying PromptForge V3 SOP to optimize or structure any prompt using the standard pattern
---

PromptForge V3 Structural Pattern — Procedură Standard de Operare

Status: ACTIVE | Versiune: 1.0 | Creat: 2026-02-28 | Regulă asociată: PROMPT-H-002 | Scope: Pattern structural obligatoriu pentru prompturi de audit/decizie/producție, derivat din benchmark prompt-genie 2026-02-28.

## 1. Problema
Genie scria prompturi (V1/V2) fără: algoritm de gândire explicit, constrângeri cantitative, interdicții de hedging, thresholds numerice obligatorii în output. Rezultat: Opus producea răspunsuri mai puțin precise și mai puțin executabile decât cu V3.
Diferențe cheie V1/V2 vs V3: (1) You are X → Act as world-class X, (2) lipsă ## Approach, (3) lipsă ## Instructions separat, (4) zero constrângeri cantitative, (5) zero interdicții de hedging.

## 2. Procedura
Pas 1 — Persona: Act as a world-class [Specialist] specializing in [Domain] (superlativ + verb activ).
Pas 2 — Adaugă ## Approach SEPARAT: algoritmul de gândire înainte de output (CUM evaluezi, ce determini per item).
Pas 3 — ## Response Format cu bullet counts: nu doar headers ci și numărul exact de bullets per secțiune (ex: 2-4 bullets, 3 concrete actions).
Pas 4 — ## Formatting Rules ca secțiune separată: no personal pronouns, no hedging words, word count <=N, >=1 comandă concretă, thresholds numerice obligatorii.
Pas 5 — ## Instructions SEPARAT de format: valori și priorități (ce primește precedență, cum tratezi riscul).

## 3. Cortex Logging
După fiecare benchmark prompt-genie: salvează în self-improve-prompting cu score comparativ Genie vs V3 pe 5 criterii (Clarity, Specificity, Structure, Context-awareness, Actionability).

## 4. Enforcement Loop
WHERE: WISH Step S + PromptForge Phase 2 (Optimize) — la orice prompt de audit/producție
WHEN: Trigger: prompt implică decizie ireversibilă SAU audit de producție SAU depth D3+
HOW: Prompt fără ## Approach → violation PROMPT-H-002; fără threshold numeric → violation; fără ## Instructions separat → flag warning.
CONNECT: PROMPT-H-002 → PromptForge v2.1 (checklist integrat); self-improve-prompting → benchmark periodic prompt-genie; procedure-health.json → entry PROMPTFORGE-V3-PATTERN

## 5. Dependențe
PromptForge v2.1: memory/promptforge.md (secțiunea V3 Structural Pattern) | prompt-genie API: benchmark periodic | self-improve-prompting: colecție Cortex pentru training insights
