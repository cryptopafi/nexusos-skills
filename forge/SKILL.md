---
name: forge
description: |
  Create a new NexusOS procedure following the FORGE standard template (v1.4). Use when Pafi says "forge [procedure name]", "creează procedură pentru X", "adaugă procedură", "new procedure", or when any new reusable workflow needs to be documented as a NexusOS procedure.
  ANTI-PATTERN: Do NOT use for one-off task execution, Codex briefs, or skill creation (use skill-creator instead). Do NOT use for auditing existing procedures (use /audit).
version: 1.0.0
user-invocable: true
---

## Procedure Reference
**Source**: `/Users/pafi/.nexus/procedures/FORGE.md`
**Read the full procedure before executing.**

## Quick Summary
FORGE creează proceduri NexusOS cu structura standard §1-§4. Orice procedură fără enforcement loop (§4) sau fără regulă asociată este considerată incompletă (META-H-002). Procedura se finalizează cu 2 VK-uri obligatorii și Cortex save.

## Input Validation

Before executing any step, validate the following inputs. Abort with a clear error message if any required field is missing.

| Input | Required | Valid Values | Error if Missing |
|---|---|---|---|
| `procedure_name` | YES | non-empty string, no spaces (use dashes) | "Procedure name is required. Usage: forge <name>" |
| `domain` | YES | `operational` \| `training` | Ask user before continuing |
| `scope` | YES | one-sentence description | Ask user: "What does this procedure solve?" |
| `rule_id` | NO | `RULE-*` identifier or `"Pending"` | Default to `"Pending — de identificat"` |

If `procedure_name` contains spaces, auto-convert to kebab-case and notify the user.

## Edge Cases

| Scenario | Detection | Behavior |
|---|---|---|
| Procedure file already exists at target path | `Glob` for `{PROCEDURE-NAME}.md` before write | Abort → ask user: OVERWRITE / RENAME / CANCEL |
| `procedure-health.json` missing entirely | File read returns 404 / not found | Create new file with `{}` before appending entry |
| Cortex unavailable | `cortex_store` throws or session startup shows "Cortex unavailable" | Skip Cortex save, emit warning `⚠️ [CORTEX] unavailable — save skipped`, mark VK with `CORTEX:SKIP` |
| Rule ID does not exist in `~/.nexus/rules/` | Glob returns no match | Set `rule_id: "Pending"`, add TODO in procedure header |
| Training domain with no subdirectory | Target path `training/{domain}/` does not exist | Create directory before writing file |
| Enforcement loop incomplete at publish time | Any WHERE/WHEN/HOW/CONNECT field is empty | Block ACTIVE status, keep `Status: DRAFT`, emit `❌ [FORGE] §4 incomplete — cannot mark ACTIVE` |

## Error Contract

| Error Code | Condition | Action | Recovery |
|---|---|---|---|
| `FORGE-E-001` | `procedure_name` is empty or not provided | Abort immediately | Re-invoke with name: `forge <procedure-name>` |
| `FORGE-E-002` | Target file already exists | Prompt user OVERWRITE / RENAME / CANCEL | User selects action before continuing |
| `FORGE-E-003` | `procedure-health.json` write fails (lock, permissions) | Emit error, do NOT retry silently | Report path and error; user must resolve manually |
| `FORGE-E-004` | Cortex save fails | Warn and continue (non-blocking) | Procedure is still saved locally; Cortex sync deferred |
| `FORGE-E-005` | §4 Enforcement Loop left incomplete | Block status → ACTIVE, keep DRAFT | Fill WHERE/WHEN/HOW/CONNECT before re-running checklist |
| `FORGE-E-006` | File write to procedures path fails | Abort, report full path and OS error | Verify `~/.nexus/procedures/` is writable |

Errors `FORGE-E-001`, `FORGE-E-002`, `FORGE-E-006` are **blocking** (halt execution).
Errors `FORGE-E-004` are **non-blocking** (warn and continue).
Errors `FORGE-E-003`, `FORGE-E-005` are **blocking post-write** (procedure saved but not activated).

## Key Steps

### Pas 0: SKILL-SEARCH Gate
Dacă procedura produce un **skill** (nu o procedură operațională), caută întâi:
1. `~/.claude/skills/` — skills locale
2. `~/.claude/plugins/genie-training/skills/` — skills de training
3. Cortex: `cortex_search "skill:<name>"`

Dacă găsești → prezintă opțiunile Pafi (INSTALL / COPY-REBUILD). Dacă nu găsești → construiești de la zero.

Emit: `🔍 [SKILL-SEARCH] căutat în: {surse} | rezultat: FOUND({name}) / NOT_FOUND → building from scratch`

### Pas 1: Colectează context
Întreabă (sau extrage din conversație):
- **Problema**: Ce rezolvă această procedură? De ce există?
- **Domeniu**: Operațional (NexusOS, infra, sync) sau Training (skill PE, business)?
- **Regulă**: Există o regulă hard/standard asociată? (verifică `~/.nexus/rules/`)
- **Trigger**: Când se activează? Manual sau automat?

### Pas 2: Draft procedură — completează template-ul

Folosește structura exactă din FORGE.md:

```
# {TITLU} — Procedură Standard de Operare

**Status**: DRAFT
**Creat**: {data azi}
**Versiune**: 1.0
**Regulă asociată**: {RULE-ID sau "Pending — de identificat"}
**Scope**: {O propoziție}

## 1. Problema
{Ce problemă rezolvă, de ce există, ce se întâmplă fără ea}

## 2. Procedura
### Pas 1: {NUME}
### Pas 2: {NUME}
...

### Test Cases (minim 1)
1. Normal flow: {situație tipică → output așteptat}
2. Edge case: {situație limită → comportament}
3. Failure case: {când NU se aplică}

## 3. Cortex Logging
{Ce se salvează, collection, metadata cu: type, procedure, rule_id, has_enforcement_loop: true, forge_version: "1.4"}

## 4. Enforcement Loop
### WHERE
### WHEN
### HOW (violation detection)
### CONNECT
### VERIFY
[ ] Procedura executată complet?
[ ] Output satisface §1?
[ ] VK emis?

### MODEL ROUTING
```

### Pas 3: Completează Enforcement Loop (§4) — OBLIGATORIU
Nu există procedură fără enforcement loop. Completează:
- **WHERE**: în ce gate/step este verificată (WISH, Post-H, daemon, etc.)
- **WHEN**: ce event o declanșează
- **HOW**: cum se detectează violarea (checks, runner script)
- **CONNECT**: leagă-o de regula asociată + `procedure-health.json`

### Pas 4: Pre-Publication Checklist
Bifează TOATE înainte de a marca ACTIVE:
- [ ] Regulă asociată există
- [ ] Enforcement loop complet (WHERE/WHEN/HOW/CONNECT/VERIFY)
- [ ] Descrie CE nu CUM (zero cod inline >10 linii)
- [ ] Test cases documentate
- [ ] Entry în `procedure-health.json`
- [ ] forge_version: "1.4" în Cortex metadata

### Pas 5: Salvează fișierul
Path standard:
- Operațional: `~/.nexus/procedures/{PROCEDURE-NAME}.md`
- Training: `~/.nexus/procedures/training/{domain}/{procedure-file}.md`

Verifică că directorul țintă există înainte de scriere (vezi Edge Cases — Training domain).

### Pas 5b: Actualizează `procedure-health.json` — cu write guard

`procedure-health.json` poate fi scris concurent de mai mulți agenți sau procese. Folosește următorul protocol:

1. **Lockfile check**: înainte de write, verifică existența `~/.nexus/state/procedure-health.lock`
   - Dacă lock există și are vârstă < 30s → abort write, emit `⚠️ [FORGE] procedure-health.json locked — retry in 5s` și re-încearcă o singură dată
   - Dacă lock există și are vârstă ≥ 30s → lock este stale, șterge-l și continuă
2. **Creează lockfile**: `~/.nexus/state/procedure-health.lock` cu conținut `{agent: "forge", pid: <pid>, ts: <iso-timestamp>}`
3. **Read-modify-write**:
   - Citește `procedure-health.json` (sau inițializează `{}` dacă nu există — `FORGE-E-003` dacă citirea eșuează din alt motiv)
   - Adaugă entry-ul noii proceduri
   - Scrie fișierul înapoi atomic
4. **Șterge lockfile** imediat după write reușit (sau dacă write eșuează)
5. Dacă write eșuează → emit `FORGE-E-003`, raportează path și eroare

### Pas 6: Cortex save + VK-uri

Salvează în Cortex:
```json
{
  "text": "{titlu procedură} | scope: {scope} | rule: {RULE-ID} | enforcement: complete",
  "collection": "procedures",
  "metadata": {
    "type": "procedure",
    "procedure": "{PROCEDURE-NAME}",
    "rule_id": "{RULE-ID}",
    "has_enforcement_loop": true,
    "forge_version": "1.4",
    "tags": ["{domeniu}", "procedure", "forge"]
  }
}
```

Emit **ambele VK-uri** (per VK-H-001):

`✅ [PROC] FORGE | §1✓ §2✓ §3✓ §4✓ VER✓ | complete`

`✅ [CORTEX] "{titlu}" | FORGE ✓ | rule: {RULE-ID} | v1.0`

## When to Use vs Alternatives

- **forge** (this): când creezi o procedură NexusOS nouă din conversație sau din lecții extrase
- **/audit**: când vrei să auditezi o procedură existentă (AUDIT-PRO NPLF)
- **skill-creator**: când output-ul dorit e un skill invocabil (SKILL.md cu evals), nu o procedură
- **codex**: când procedura implică cod care trebuie scris de Codex daemon