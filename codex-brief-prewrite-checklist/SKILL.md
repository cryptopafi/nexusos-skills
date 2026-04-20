---
name: codex-brief-prewrite-checklist
description: Use before writing any Codex brief — MODULAR compliance checklist enforcing CODEX-H-001
---

# PROCEDURE: Codex Brief Pre-Write Checklist

**Version**: 1.0 | **Architecture**: MODULAR | **Rule**: CODEX-H-001, DEV-H-013
**Cortex replaces**: eeae4c2d (text liber, non-standard)

---

## §1 PROBLEM
Genie scrie cod complet în briefuri Codex (over-specification), violând template v2.1.
Root cause: nu citește templateul ÎNAINTE de scriere, presupune că știe formatul.

## §2 PROCEDURE — Pre-Write Checklist

ÎNAINTE de a scrie orice brief în ~/.codex/genie-to-codex.md:

1. **LOAD**: Citește memory/codex-brief-template.md (templateul curent)
2. **VERIFY structure**: Am aceste secțiuni?
   - [ ] Goal (1 propoziție)
   - [ ] Context (fișiere, stare, decizii)
   - [ ] Steps (numerotate, cu checkpoint per pas)
   - [ ] Output (format exact delivery)
   - [ ] Success Criteria (checkbox-uri testabile)
   - [ ] Constraints (ce NU trebuie)
   - [ ] Safety (rate limits, costuri, riscuri)
3. **ANTI-PATTERN check**:
   - [ ] Brief < 100 linii? (dacă nu → decompose)
   - [ ] Zero cod inline? (descrie CE, nu CUM)
   - [ ] Zero implementare detaliată? (Codex decide CUM)
4. **SELF-CHECK**: Ar înțelege un developer nou ce trebuie fără codul meu?
5. **WRITE**: Abia acum scrie brieful

## §3 ENFORCEMENT LOOP

### WHERE
- WISH Step H (Flux B și C) — orice brief Codex
- Referință: codex-brief-template.md v2.1

### WHEN
- La FIECARE task scris în genie-to-codex.md
- Fără excepții, indiferent de urgență sau complexitate

### HOW
- LOAD-VERIFY-WRITE (3 pași obligatorii)
- Dacă brief depășește 100 linii → STOP, decompose în sub-tasks
- Dacă conține cod inline → STOP, rescrie ca descriere outcome

### CONNECT
- CODEX-H-001 (hard rule — template obligatoriu)
- DEV-H-013 (hard rule — Genie NU scrie cod)
- codex-brief-template.md v2.1 (templateul)
- codex-daemon.sh (parserul care execută)
- procedure-health.json (monitoring)

## §4 LESSON LEARNED
- 2026-02-27: m4-153 și m4-154 scrise cu ~280-300 linii cod complet. Pafi a observat, nu Genie.
- Fix: rescrise la ~70-75 linii, format corect, zero cod inline.
- Pattern: presupunerea că știi un format din memorie → greșeli. Citește sursa de adevăr MEREU.
