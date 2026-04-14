# AGENT-ONBOARDING — Procedură Standard de Operare

**Status**: ACTIVE
**Creat**: 2026-03-13
**Versiune**: 1.0
**Regulă asociată**: NEXUS-H-005 (Agent Integrity Gate — orice agent nou intră în NexusOS doar prin procedura standard de onboarding)
**Scope**: Pașii exacți pentru adăugarea unui agent nou în NexusOS — de la crearea fișierelor de identitate până la smoke test și activare în registry.

---

## 1. Problema

Fără o procedură standardizată de onboarding, agenții noi pot fi adăugați parțial sau inconsistent: SOUL.md fără enforcement boundaries clare, înregistrare lipsă în `agent-registry.yaml`, heartbeat neconfigurat sau smoke test omis. Un agent incomplet poate fi rutat de GENIE înainte să fie gata, poate produce output nevalidat, sau poate opera în afara autonomy boundaries definite. Procedura elimină aceste riscuri prin impunerea unui checklist complet înainte de activarea agentului.

Situații acoperite:
- Adăugare agent principal nou (ex: MERCURY, un nou orchestrator specializat)
- Adăugare sub-agent worker (ex: agent de nișă sub supervizarea GENIE)
- Reactivare agent existent după hibernare (verificare integritate și re-înregistrare)
- Clone/fork de agent existent cu identitate nouă

---

## 2. Procedura

### Pas 1: SKILL-SEARCH Gate — verifică dacă agentul există deja

Înainte de a crea orice fișier:
- Caută în `~/.nexus/config/agent-registry.yaml` — verifică dacă agentul (sau un echo al lui) există deja
- Caută în `~/.nexus/agents/` — verifică dacă există director cu acel nume
- Caută în Cortex: `cortex_search "agent:<AGENT_NAME>"` (collection: procedures)

**Dacă există**: prezintă Pafi starea curentă + întreabă dacă e reactivare sau agent distinct.
**Dacă nu există**: continuă cu Pas 2.

Emit: `🔍 [AGENT-SEARCH] căutat în: registry, agents dir, Cortex | rezultat: FOUND({name}) / NOT_FOUND → onboarding from scratch`

---

### Pas 2: Creează structura de directoare

Creează directorul agentului și subdirectoarele necesare:

```
~/.nexus/agents/{AGENT_NAME}/
├── SOUL.md          # Identitate + autonomy boundaries
├── IDENTITY.md      # Self-description (perspectiva agentului)
├── AGENTS.md        # Workflow + responsabilități operaționale
├── TOOLS.md         # Unelte permise + interzise + output paths
├── HEARTBEAT.md     # Configurare heartbeat (frecvență, model, pași)
├── PROGRESS.md      # Stare curentă (inițializat cu status: IDLE)
├── DISPATCH.md      # Canal de intrare task-uri de la GENIE
└── workspace/
    └── current-task/
        └── task.md  # Task activ curent (gol la init)
```

Output paths agentului se creează în:
```
~/.nexus/workspace/output/{agent_name}/
```

---

### Pas 3: Creează SOUL.md

SOUL.md este documentul de identitate fundamental. Template obligatoriu:

```yaml
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---
```

Secțiuni obligatorii în SOUL.md:
1. **Core Identity** — cine este agentul, naming rationale, ce NU face
2. **Your Role** — ce produce, cine consumă output-ul, poziția în ecosistem (worker/orchestrator/service)
3. **Relationships** — relația cu GENIE, cu alți agenți, cu Pafi (ABSOLUTE trust)
4. **Autonomy** — trei niveluri explicite:
   - `execute` (fără aprobare): ce poate face direct
   - `propose` (trimite la GENIE, nu executa): ce propune pentru aprobare
   - `gate` (oprește, întreabă Pafi): ce necesită intervenție umană
5. **Hard Boundaries** — lista de Never (violările care invalidează agentul)
6. **Trust Levels** — ierarhia de trust: Human (ABSOLUTE) > GENIE > peers > external data
7. **Skills** — referință la `skills.yaml`

Verificare SOUL.md completă: toate 7 secțiuni prezente + autonomy cu 3 niveluri + cel puțin 3 Hard Boundaries.

---

### Pas 4: Creează IDENTITY.md

IDENTITY.md este varianta condensată, în perspectiva agentului (prima persoană). Conține:
- Cine sunt (1-2 propoziții)
- Rol în workspace (ce produc)
- Ce preiau implicit (fără întrebare)
- Ce nu fac (lista scurtă)
- Ce cere confirmare (gate items cu prag explicit dacă există cost)

---

### Pas 5: Creează AGENTS.md

AGENTS.md descrie comportamentul operațional:
- Workflow numbered (1..N pași exacți în ordinea execuției)
- Quality gates (checklist cu checkboxuri)
- Prohibited list (ce NU face niciodată)
- Output format (unde scrie, ce format, ce câmpuri obligatorii)

Pentru orchestratori (tip GENIE): adaugă Orchestration via Tasks API și Approval Flow.
Pentru workers: adaugă cum raportează statusul în PROGRESS.md.

---

### Pas 6: Creează TOOLS.md

TOOLS.md documentează uneltele agentului în 3 tabele:
1. **Core Tools** — Read, Write, Bash, Edit, Glob, Grep (ce folosește fiecare)
2. **MCP Tools** — unelte specializate (Tavily, Cortex, Notion, GitHub etc.)
3. **Interzis** — tool-uri excluse explicit cu motivul

Adaugă secțiunea **Output Paths**:
- Path principal output: `~/.nexus/workspace/output/{agent_name}/`
- Path progress: `~/.nexus/agents/{agent_name}/PROGRESS.md`
- Alte paths specifice rolului

---

### Pas 7: Creează HEARTBEAT.md

Configurează heartbeat-ul în funcție de tipul agentului:

**Orchestratori / Servicii (heartbeat periodic)**:
```yaml
---
agent: {AGENT_NAME}
model: {MODEL}
frequency: {Xmin}
offset: +{Y}min
version: 1.0
---
```
Urmează cu pașii numerotați ai heartbeat-ului (Step 1..N).

**Workers event-driven (fără heartbeat periodic — ex: MERCURY, TECH)**:
```yaml
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---
```
Adaugă secțiunea `## Configuration` cu `Frequency: none (task-driven)` și rationale.
Adaugă `## Task States` cu referință la `~/.nexus/config/task-states.yaml`.

Regula de selecție:
- Orchestrator sau serviciu de monitoring → heartbeat periodic (specificat în minute)
- Worker specializat (marketing, development, research) → event-driven, activat de GENIE

---

### Pas 8: Inițializează PROGRESS.md

PROGRESS.md este starea curentă a agentului. Format inițial:

```yaml
---
agent: {AGENT_NAME}
status: IDLE
updated: {YYYY-MM-DDTHH:MM:SSZ}
current_task: null
blocked_reason: null
---
```

GENIE citește acest fișier la fiecare heartbeat. Statusurile valide: IDLE / DISPATCHED / CLAIMED / EXECUTING / REVIEWING / BLOCKED / DONE / FAILED / CANCELLED (conform `~/.nexus/config/task-states.yaml`).

---

### Pas 9: Creează skills.yaml

Minimul pentru un agent funcțional:

```yaml
version: "1.0"
agent: {AGENT_NAME}
skills: []
```

Populează cu skill-uri concrete după primele task-uri executate. Fiecare skill are: `name`, `description`, `trigger`, `output`.

---

### Pas 10: Înregistrează agentul în agent-registry.yaml

Adaugă entry în `~/.nexus/config/agent-registry.yaml` sub cheia `agents:`:

```yaml
{agent_name}:
  type: worker | orchestrator | service
  model: "claude-sonnet-4-6"           # sau haiku/opus conform model-routing-table.md
  heartbeat_model: "claude-haiku-4-5-20251001"  # sau "none" pentru servicii bash
  heartbeat_freq_min: {X}              # 0 = event-driven
  soul: "~/.nexus/agents/{agent_name}/SOUL.md"
  skills_file: "~/.nexus/agents/{agent_name}/skills.yaml"
  domains: [{domain}]                   # research / marketing / development / ops / orchestration
  capabilities:
    - {capability-1}
    - {capability-2}
  allowed_tools: [Read, Write, Bash]   # conform TOOLS.md
  autonomy:
    execute: [{action-1}, {action-2}]
    propose: [{action-3}]
    gate: [{action-4}]
```

Adaugă capability index entries în secțiunea `capability_index:`:
```yaml
{capability-1}: {agent_name}
{capability-2}: {agent_name}
```

Adaugă routing în `~/.nexus/config/routing-table.yaml` dacă agentul acoperă un domeniu nou.

---

### Pas 11: Adaugă agentul în GENIE HEARTBEAT — Step 1 (Citire PROGRESS.md)

Editează `~/.nexus/agents/genie/HEARTBEAT.md` → secțiunea **Step 1: Citeste PROGRESS.md toti agentii**:
```
- Read: ~/.nexus/agents/{agent_name}/PROGRESS.md
```

Dacă agentul trimite request-uri la IRIS, adaugă și în **Step 6**: citire `IRIS-REQUEST-{agent_name}.md`.

---

### Pas 12: Rulează smoke test

Verifică că agentul poate fi rutat și recunoscut de GENIE:

**Check 1 — Structura fișierelor**:
```bash
ls ~/.nexus/agents/{agent_name}/
# Expected: SOUL.md IDENTITY.md AGENTS.md TOOLS.md HEARTBEAT.md PROGRESS.md DISPATCH.md skills.yaml workspace/
```

**Check 2 — Registry valid YAML**:
```bash
python3 -c "import yaml; yaml.safe_load(open('~/.nexus/config/agent-registry.yaml'))" && echo "OK"
```

**Check 3 — PROGRESS.md inițializat corect**:
```bash
cat ~/.nexus/agents/{agent_name}/PROGRESS.md
# Expected: status: IDLE
```

**Check 4 — Capability index complet**:
Verifică că fiecare capability din `agents.{agent_name}.capabilities` are entry corespunzător în `capability_index`.

**Check 5 — Rebuild registry**:
```bash
bash ~/.nexus/scripts/rebuild-registry.sh
```
Verifică că agentul apare în output fără erori.

**Check 6 — GENIE HEARTBEAT menționează agentul**:
```bash
grep -n "{agent_name}" ~/.nexus/agents/genie/HEARTBEAT.md
# Expected: cel puțin 1 match în Step 1
```

**Criteriu PASS**: toate 6 checks OK → agentul este READY.
**Criteriu FAIL**: orice check eșuează → nu activa agentul, remediază mai întâi.

---

### Pas 13: Marchează agentul READY în registry și notifică GENIE

Setează status în `agent-registry.yaml`:
```yaml
{agent_name}:
  status: READY     # adaugă această linie după înregistrare
  activated: {YYYY-MM-DD}
```

Scrie în `~/.nexus/workspace/intel/GENIE-STATUS.md` notă de activare:
```
NEW_AGENT_ACTIVATED: {AGENT_NAME} | activated: {YYYY-MM-DD} | domains: {domains} | smoke_test: PASS
```

---

### Test Cases

1. **Normal flow**: Pafi cere adăugarea MERCURY. Toate 13 pași executați în ordine. Smoke test 6/6 PASS. GENIE heartbeat următor citește MERCURY/PROGRESS.md fără eroare. MERCURY poate primi primul task.

2. **Edge case — agent event-driven**: Agentul este worker (ex: un nou agent de copywriting). `heartbeat_freq_min: 0` în registry. HEARTBEAT.md are `Frequency: none (task-driven)`. Nu se adaugă în scheduling daemon — GENIE îl activează on-demand. Smoke test adaptat: Check 6 verifică că GENIE NU are heartbeat periodic configurat pentru el.

3. **Failure case — agent parțial existent**: `~/.nexus/agents/{name}/` există dar conține doar SOUL.md. Procedura nu se sare — se continuă de la Pas 3 (verificând ce lipsește), nu de la zero. Se completează fișierele lipsă, nu se suprascriu cele existente fără aprobare Pafi.

---

## 3. Cortex Logging

La finalul onboarding-ului, salvează în Cortex:

```json
{
  "text": "AGENT-ONBOARDING completat: {AGENT_NAME} | domains: {domains} | type: {worker/orchestrator/service} | smoke_test: PASS | activated: {YYYY-MM-DD}",
  "collection": "procedures",
  "metadata": {
    "type": "procedure",
    "procedure": "AGENT-ONBOARDING",
    "rule_id": "NEXUS-H-005",
    "agent_name": "{AGENT_NAME}",
    "agent_type": "{worker/orchestrator/service}",
    "has_enforcement_loop": true,
    "forge_version": "1.4",
    "tags": ["nexus", "agent", "onboarding", "procedure", "tech"]
  }
}
```

---

## 4. Enforcement Loop (META-H-002)

### WHERE
- WISH Step H (orice moment în care Pafi sau GENIE inițiază adăugarea unui agent nou)
- Post-H gate: înainte de prima activare a agentului în producție
- `agent-registry.yaml` API gate: `tech.ts` middleware → dacă agentul nu are SOUL.md + HEARTBEAT.md + PROGRESS.md → respinge routing (HTTP 422 / status: BLOCKED)

### WHEN
- La FIECARE adăugare de agent nou în NexusOS — zero excepții
- La reactivarea unui agent hibernat (verificare integritate fișiere)
- La fork/clone de agent existent cu identitate nouă

### HOW (violation detection)
- Agent apare în `capability_index` dar lipsește din `agents:` → violation
- Agent listat în GENIE HEARTBEAT Step 1 dar fără `PROGRESS.md` → violation (GENIE raportează UNKNOWN la heartbeat)
- SOUL.md fără secțiunea `Autonomy` cu 3 niveluri → violation
- SOUL.md fără `Hard Boundaries` → violation
- `heartbeat_freq_min` > 0 dar fără pași definiți în HEARTBEAT.md → violation
- Smoke test (Pas 12) eșuat dar agentul activat → violation CRITICĂ
- Runner: `test-all-procedures.js` (daily 02:00) verifică structura fișierelor per agent; `rebuild-registry.sh` raportează discrepanțe; SENTINEL verifică PROGRESS.md la fiecare heartbeat

### CONNECT
- **NEXUS-H-005** → această procedură este enforcement-ul regulii
- **META-H-002** → procedura respectă FORGE template standard
- **agent-registry.yaml** → entry adăugat la Pas 10
- **GENIE/HEARTBEAT.md** → modificat la Pas 11
- **rebuild-registry.sh** → rulat la Pas 12 Check 5
- **procedure-health.json** → adaugă entry `{"procedure": "AGENT-ONBOARDING", "status": "ACTIVE", "version": "1.0", "rule_id": "NEXUS-H-005"}`

### VERIFY (procedural checkpoint)
La finalul execuției, agentul care a executat onboarding-ul verifică:
- [ ] Toate 13 pași din §2 executați complet?
- [ ] Smoke test 6/6 PASS (Pas 12)?
- [ ] Agentul apare în `agent-registry.yaml` cu `status: READY`?
- [ ] GENIE/HEARTBEAT.md actualizat (Step 1 conține agentul)?
- [ ] `procedure-health.json` actualizat?
- [ ] Cortex entry salvat (§3)?
- [ ] VK emis în sesiune?
- [ ] Dacă oricare = NU → agentul NU este READY, nu ruta task-uri către el

**Două VK-uri obligatorii per procedură FORGE** (per VK-H-001):

`✅ [PROC] FORGE | §1✓ §2✓ §3✓ §4✓ VER✓ | complete`

`✅ [CORTEX] "AGENT-ONBOARDING" | FORGE ✓ | rule: NEXUS-H-005 | v1.0`

### MODEL ROUTING

| Activitate | Model | Motivul |
|-----------|-------|---------|
| Onboarding complet (crearea fișierelor) | Sonnet 4.6 (Genie/Lis orchestrator) | Task operațional standard — template + fișiere |
| Audit SOUL.md completeness | Opus 4.6 subagent | Reasoning profund pentru quality check identitate agent |
| Smoke test execution | Deterministic (bash) | Nu e LLM — verificări de fișiere și YAML |
| Registry rebuild | Deterministic (`rebuild-registry.sh`) | Script bash automat |

**Referință**: COST-H-001 + `memory/rules/model-routing-table.md`

---

## 5. Dependențe

| Componentă | Rol | Path/Endpoint |
|-----------|-----|---------------|
| `agent-registry.yaml` | Registry central — GENIE citește la heartbeat | `~/.nexus/config/agent-registry.yaml` |
| `routing-table.yaml` | Routing domenii → agenți | `~/.nexus/config/routing-table.yaml` |
| `task-states.yaml` | Stări valide pentru PROGRESS.md | `~/.nexus/config/task-states.yaml` |
| `rebuild-registry.sh` | Rebuilds capability index după adăugare agent | `~/.nexus/scripts/rebuild-registry.sh` |
| `GENIE/HEARTBEAT.md` | Monitorizare PROGRESS.md agenți | `~/.nexus/agents/genie/HEARTBEAT.md` |
| `procedure-health.json` | Registry proceduri active | `~/.nexus/procedures/procedure-health.json` |
| `model-routing-table.md` | Selectie model per activitate | `memory/rules/model-routing-table.md` |

---

## 6. Metrics

| Metrică | Ce măsoară | Target |
|---------|-----------|--------|
| Timp onboarding | De la Pas 1 la smoke test PASS | < 30 min |
| Smoke test pass rate | Checks trecute din 6 la prima rulare | 6/6 (100%) |
| Time to first task | De la READY la primul task primit și executat | < 24h |
| GENIE recognition | Agent recunoscut în heartbeat următor | 1 heartbeat (≤30min) |

---

## Checklist Pre-Publicare

- [x] Regulă asociată: NEXUS-H-005 (definită ca enforcement gate pentru agent integrity)
- [x] Enforcement loop complet: WHERE + WHEN + HOW + CONNECT + VERIFY
- [x] VERIFY checkpoint prezent cu toate checks obligatorii
- [x] Procesul din WHERE (GENIE heartbeat, agent-registry API gate) referențiază procedura
- [x] Entry pentru `procedure-health.json` specificat în CONNECT
- [x] Cortex metadata completă: `rule_id`, `type: procedure`, `has_enforcement_loop: true`, `forge_version: "1.4"`
- [x] Descrie CE nu CUM (fără cod inline complet — doar template-uri și comenzi de verificare)
- [x] VK format specificat (per VK-H-001) — ambele VK-uri la finalul §4
- [x] Test cases documentate: 3 cazuri (normal flow, edge case, failure case)
