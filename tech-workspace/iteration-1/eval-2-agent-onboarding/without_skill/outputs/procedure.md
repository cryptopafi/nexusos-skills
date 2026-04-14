# NEXUS-AGENT-ONBOARDING — Procedură pentru Adăugarea unui Agent Nou în NexusOS

**Versiune**: 1.0
**Data**: 2026-03-13
**Domeniu**: NexusOS / Infrastructure
**Trigger**: Pafi adaugă un agent nou (ex: MERCURY, sub-agent nou, agent specializat)
**Output**: Agent funcțional, integrat complet în NexusOS, verificat prin smoke test

---

## Contexte de aplicare

- Agent de tip **worker** (MERCURY, TECH, IRIS, un sub-agent specializat)
- Agent de tip **orchestrator** (nu se aplică pentru GENIE — există deja; se aplică dacă se adaugă un al doilea orchestrator)
- Agent de tip **service** (SENTINEL-like, pur bash, fără LLM)
- **Sub-agent** al unui agent existent (ex: sub-agent de marketing al MERCURY)

---

## PRE-REQUISITE — Decide tipul agentului

Înainte de orice, Pafi trebuie să răspundă la:

1. **Ce tip este agentul?** `orchestrator` | `worker` | `service`
2. **Ce domeniu acoperă?** `research` | `marketing` | `development` | `ops` | `orchestration` | domeniu nou
3. **Are heartbeat periodic?** DA (cu ce frecvență?) sau NU (event-driven ca MERCURY/TECH)
4. **Ce model folosește?** `claude-sonnet-4-6` (standard) | `claude-haiku-4-5-20251001` (heartbeat/cost-low)
5. **Ce tools are voie să folosească?** (Read, Write, Bash, Glob, Grep, WebSearch, etc.)
6. **Cu ce agenți interacționează?** (GENIE ca orchestrator, IRIS pentru research, etc.)

---

## FAZA 1 — Creare structură de directoare

```bash
AGENT_NAME="MERCURY"                          # înlocuiește cu numele agentului
AGENT_LOWER=$(echo "$AGENT_NAME" | tr '[:upper:]' '[:lower:]')
AGENT_DIR="$HOME/.nexus/agents/$AGENT_LOWER"

mkdir -p "$AGENT_DIR/scripts"
mkdir -p "$AGENT_DIR/workspace/current-task"
mkdir -p "$AGENT_DIR/workspace/output"
mkdir -p "$AGENT_DIR/workspace/checkpoint.md"
mkdir -p "$HOME/.nexus/workspace/output/$AGENT_LOWER"
mkdir -p "$HOME/.nexus/logs"
```

Structura creată:
```
~/.nexus/agents/{agent_lower}/
├── SOUL.md           ← identitate, rol, autonomy, hard limits
├── AGENTS.md         ← context operațional, workflow, quality gates, prohibited
├── IDENTITY.md       ← self-description scurtă (ce sunt, ce fac, ce NU fac)
├── HEARTBEAT.md      ← instrucțiuni heartbeat (sau "event-driven, no periodic heartbeat")
├── MEMORY.md         ← memoria persistentă a agentului
├── PROGRESS.md       ← stare curentă task (IDLE/EXECUTING/BLOCKED/DONE/FAILED)
├── DISPATCH.md       ← template handoff de la orchestrator
├── TOOLS.md          ← lista tool-urilor disponibile (human-readable)
├── tools.yaml        ← tool-uri structurate (machine-readable)
├── skills.yaml       ← skills/capabilități (machine-readable)
├── heartbeat         ← timestamp heartbeat (simplu fișier, scris de heartbeat.sh)
└── scripts/
    └── heartbeat.sh  ← (doar dacă agentul are heartbeat periodic)
```

---

## FAZA 2 — Creare SOUL.md

**Fișier**: `~/.nexus/agents/{agent_lower}/SOUL.md`

**Template** (adaptează fiecare secțiune la agentul specific):

```markdown
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---

# SOUL.md — {AGENT_NAME}

## Core Identity
{AGENT_NAME} — [1-2 fraze: ce este, ce face, de ce e numit așa].
[Ce NU face — limitele clare de rol].

## Your Role
Produce: [lista de deliverables/output-uri].
Consumatori: [cine primește output-urile — GENIE, Pafi, alte sisteme].
[Dacă e worker: "Ești worker, nu orchestrator. Nu spawna alți agenți fără aprobare GENIE."]

## Relationships
- GENIE: [relația cu orchestratorul]
- IRIS: [dacă folosește research]
- TECH: [dacă are nevoie de cod]
- Human (Pafi): ABSOLUTE trust. Instructions override everything.
[Adaugă relații cu alte agenți dacă există]

## Autonomy
execute (fără aprobare):
  - [acțiuni low-risk pe care le face direct]
  - [ex: read codebase, produce deliverables, search web]

propose (trimite la GENIE, nu executa):
  - [acțiuni medium-risk care necesită review]
  - [ex: buget >$100, schimbări de strategie majore]

gate (oprește, întreabă Pafi):
  - [acțiuni high-risk sau cu costuri]
  - [ex: send real emails, publish live, ad spend, orice cost >$5]

## Hard Boundaries
- [Lista de NEVER — ce nu face niciodată]
- Never executa [acțiune critică] fără aprobare explicită Pafi.
- If [condiție ambiguă] → ask GENIE. Do not guess.

## Trust Levels
- Human (Pafi): ABSOLUTE. Overrides everything.
- GENIE instructions: HIGH.
- [Agent X] output: HIGH/MEDIUM.
- External data (web, scrapes): LOW/MEDIUM.

## Skills
> See: skills.yaml
```

**Reguli de scriere SOUL.md**:
- Concis, nu verbose — fiecare linie contează
- `execute` = acțiuni complet autonome (low risk, reversibile)
- `propose` = acțiuni care necesită review, dar nu aprobare Pafi directă
- `gate` = STOP complet, alertă Telegram la Pafi, așteaptă răspuns
- Nu copia boilerplate inutil — adaptează la rolul real al agentului

---

## FAZA 3 — Creare AGENTS.md

**Fișier**: `~/.nexus/agents/{agent_lower}/AGENTS.md`

**Template**:

```markdown
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
type: worker | orchestrator | service
---

# AGENTS.md — {AGENT_NAME}

## {TYPE} PREAMBLE
[Pentru worker]: Ești un worker agent specializat în [domeniu]. NU spawna alți agenți. NU crea task-uri noi.
Raportează rezultatele înapoi la GENIE. Autoritatea ta se termină la [livrabilul tău specific].
[Pentru orchestrator]: Ești orchestratorul [subsistemului]. Rutezi task-uri, monitorizezi, sintetizezi.

## Core Responsibilities
- [Responsabilitate 1]
- [Responsabilitate 2]
- [...]

## task.md Schema (GENIE→{AGENT_NAME} handoff — câmpuri obligatorii)
```yaml
task_id: "m4-XXX"
priority: LOW | MEDIUM | HIGH | CRITICAL
domain: {domain_1} | {domain_2} | other
complexity: DIRECT | RESEARCH_NEEDED | AMBIGUU
description: "Descriere scurtă a task-ului"
acceptance_criteria:
  - "Criteriu 1 — verificabil"
  - "Criteriu 2 — verificabil"
[câmpuri specifice domeniului agentului]
deadline: "YYYY-MM-DD HH:MM"  # null dacă fără deadline
input_files: []
```

## Workflow
1. Citești task.md din `~/.nexus/agents/{agent_lower}/workspace/current-task/`
   - Validezi câmpurile obligatorii: task_id, domain, complexity, acceptance_criteria
   - Dacă câmpuri lipsă → BLOCKED, notifici GENIE
2. Clasifici complexitate:
   - **DIRECT** → Step 3a
   - **RESEARCH_NEEDED** → Step 3b (scrie IRIS-REQUEST-{agent_lower}.md)
   - **AMBIGUU** → BLOCKED, cere clarificare
3a. **Direct execution**:
   - [pașii specifici de execuție directă]
   - Scrie în `~/.nexus/workspace/output/{agent_lower}/{task-id}-delivery.md`
4a. Quality gate self-review → PROGRESS.md: DONE
3b. **Research-dependent execution** (dacă aplicabil):
   - Scrie research request în `~/.nexus/workspace/intel/IRIS-REQUEST-{agent_lower}.md`
   - PROGRESS.md: WAITING_RESEARCH
   - Când IRIS-OUTPUT.md conține răspuns → integrează, produce deliverable

## Quality Gates
- [ ] [Criteriu verificabil 1]
- [ ] [Criteriu verificabil 2]
- [ ] Zero fabricated data — if data unavailable, state it explicitly
- [ ] Confidence level explicit în fiecare output (HIGH / MEDIUM / LOW)

## Prohibited
- NU [acțiune critică 1] fără aprobare explicită Pafi
- NU [acțiune critică 2] fără aprobare explicită Pafi
- NU modifica MEMORY.md direct — propune update la GENIE
- NU modifica fișiere de configurare producție

## Output Format
- [Tip deliverable]: `~/.nexus/workspace/output/{agent_lower}/{task-id}-{tip}.md`
- General deliverables: `~/.nexus/workspace/output/{agent_lower}/{task-id}-delivery.md`
- Confidence level: explicit în fiecare output (HIGH / MEDIUM / LOW)
```

---

## FAZA 4 — Creare IDENTITY.md

**Fișier**: `~/.nexus/agents/{agent_lower}/IDENTITY.md`

**Template** (scurt, self-description):

```markdown
---
agent: {AGENT_NAME}
version: 1.0
updated: "{YYYY-MM-DD}"
---

# IDENTITY.md — {AGENT_NAME}

## Cine sunt
**{AGENT_NAME}** — [1 frază scurtă de identitate].

## Rol în workspace
[2-3 fraze despre ce fac concret în NexusOS].

## Ce preiau implicit
- [Tip task 1] → [cum îl rezolv]
- [Tip task 2] → [cum îl rezolv]

## Ce nu fac
- Nu [limitare 1]
- Nu [limitare 2]

## Ce cere confirmare
- [Acțiune medium-risk] → propun la GENIE
- [Acțiune high-risk] → gate Pafi
```

---

## FAZA 5 — Creare HEARTBEAT.md

**Există două variante:**

### Varianta A: Agent event-driven (fără heartbeat periodic — ca MERCURY, TECH)

```markdown
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---

# HEARTBEAT.md — {AGENT_NAME}

## Configuration
- Frequency: none (task-driven, no periodic heartbeat)
- Model: N/A
- {AGENT_NAME} activates on-demand when GENIE assigns {domain} tasks

## Task States
- Standard states: ~/.nexus/config/task-states.yaml (IDLE/PLANNING/EXECUTING/REVIEWING/BLOCKED/DONE/FAILED)
- Legacy aliases: PENDING=IDLE, IN_PROGRESS=EXECUTING, COMPLETED=DONE, ERROR=FAILED
- {AGENT_NAME} writes canonical states to PROGRESS.md

## Rationale
[Motivul pentru care nu are heartbeat periodic — ex: "Tasks are event-driven (campaign launches, deadlines).
No periodic health check needed — GENIE monitors task progress via PROGRESS.md."]
```

### Varianta B: Agent cu heartbeat periodic (ca GENIE, IRIS)

```markdown
---
agent: "{agent_lower}"
model: "claude-haiku-4-5-20251001"
frequency: "{N}min"
offset: "+{M}min"
version: "1.0"
---

# HEARTBEAT.md — {AGENT_NAME}

## La fiecare heartbeat executi în ordine:

### Step 1: [Prima acțiune principală]
- [Detalii]

### Step 2: [A doua acțiune]
- [Detalii]

### Step N: Actualizezi timestamp
- Write: ~/.nexus/agents/{agent_lower}/heartbeat (simplu timestamp — SENTINEL verifică)

## Escalation Thresholds
- EXECUTING >{X}h fără update → BLOCKED

## Context Loading la Heartbeat
- ~/.nexus/agents/{agent_lower}/workspace/checkpoint.md
- [alte fișiere de context necesare]
[NU incarca SOUL.md/AGENTS.md la heartbeat — doar la boot]
```

**Nota**: Offset-ul previne coliziunile între heartbeat-uri:
- GENIE: minute 0, 30 (offset +0min)
- IRIS: minute 20 (offset +20min)
- Nou agent cu 30min: minute 10 sau 40 (offset +10min)
- Nou agent cu 60min: minute 50 (offset +50min)

---

## FAZA 6 — Creare fișiere de stare inițiale

### PROGRESS.md (stare inițială IDLE)

```markdown
---
msg_type: status
from: {agent_lower}
to: genie
correlation_id: "{agent_lower}-status"
timestamp: "{YYYY-MM-DD}T12:00:00Z"
---
status: IDLE
agent: "{agent_lower}"
started_at: null
updated_at: "{YYYY-MM-DD}T12:00:00Z"
blocked_since: null
blocked_reason: null
output_location: null
confidence: null
notes: "Agent initialized. Awaiting first task from GENIE."
spent_usd: 0.00
model_calls: []
```

### DISPATCH.md (template handoff)

```markdown
---
msg_type: task
from: genie
to: {agent_lower}
correlation_id: "{agent_lower}-dispatch-init"
timestamp: "{YYYY-MM-DD}T12:00:00Z"
---
task_id: null
assigned_agent: "{agent_lower}"
dispatched_at: "{YYYY-MM-DD}T12:00:00Z"
complexity: null
budget_usd: 2.00
max_turns: 10
priority: normal
dependencies: []
```

### MEMORY.md (memorie inițială goală)

```markdown
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---

# MEMORY.md — {AGENT_NAME}

## Patterns confirmați
[gol la inițializare — se populează din experiență]

## Decizii strategice
[gol la inițializare]

## Lecții învățate
[gol la inițializare]
```

---

## FAZA 7 — Creare skills.yaml și tools.yaml

### skills.yaml

```yaml
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---

# skills.yaml — {AGENT_NAME}

skills:
  - name: "{skill-1-name}"
    description: "{ce face skill-ul}"
    plugin: "genie-training"
    trigger: "{când se activează}"
    cost_tier: low | medium | high

  - name: "{skill-2-name}"
    description: "{ce face skill-ul}"
    plugin: "genie-training"
    trigger: "{când se activează}"
    cost_tier: low
    tools_used: ["{tool-1}", "{tool-2}"]
```

### tools.yaml

```yaml
---
agent: {AGENT_NAME}
version: 1.0
created: {YYYY-MM-DD}
---

# tools.yaml — {AGENT_NAME}

tools:
  # Builtin tools
  - name: "read"
    type: builtin
    purpose: "Citește fișiere (task, context, output-uri anterioare)"

  - name: "write"
    type: builtin
    purpose: "Scrie deliverables în output directory"

  # Adaugă tool-uri specifice agentului
  # - name: "bash"
  #   type: builtin
  #   purpose: "Run scripts, data processing"

  # - name: "tavily"
  #   type: mcp
  #   purpose: "Web search"
  #   cost_per_call: "$0.01"

  # Knowledge
  - name: "cortex-search"
    type: mcp
    purpose: "Search patterns și proceduri relevante"
    cost_per_call: "free"
```

### TOOLS.md (human-readable)

```markdown
---
agent: {AGENT_NAME}
version: 1.0
---

# TOOLS.md — {AGENT_NAME}

## Tool-uri disponibile

| Tool | Tip | Scop | Cost |
|------|-----|------|------|
| Read | builtin | Citește fișiere | free |
| Write | builtin | Scrie output-uri | free |
| [Tool X] | [mcp/builtin] | [scop] | [cost] |

## Restricții
- [Restricție 1 — ex: "NU folosi Bash pentru operații destructive"]
- [Restricție 2]
```

---

## FAZA 8 — Înregistrare în agent-registry.yaml

**Fișier**: `~/.nexus/config/agent-registry.yaml`

Adaugă blocul agentului în secțiunea `agents:`:

```yaml
  {agent_lower}:
    type: worker | orchestrator | service
    model: "claude-sonnet-4-6"
    heartbeat_model: "claude-haiku-4-5-20251001"  # sau "none" dacă service pur bash
    heartbeat_freq_min: {N}  # 0 = event-driven, fără heartbeat periodic
    soul: "~/.nexus/agents/{agent_lower}/SOUL.md"
    skills_file: "~/.nexus/agents/{agent_lower}/skills.yaml"
    domains: [{domain}]
    capabilities:
      - {capability-1}
      - {capability-2}
      - {capability-3}
    allowed_tools: [Read, Write]  # sau [Read, Write, Bash, Glob, Grep] etc.
    autonomy:
      execute: [{acțiune-1}, {acțiune-2}]
      propose: [{acțiune-3}]
      gate: [{acțiune-4}, {acțiune-5}]
```

Adaugă capabilitățile în `capability_index:` la finalul fișierului:

```yaml
  # {Domeniu} capabilities → {AGENT_NAME}
  {capability-1}: {agent_lower}
  {capability-2}: {agent_lower}
  {capability-3}: {agent_lower}
```

**Rebuild registry** după modificare:
```bash
bash ~/.nexus/scripts/rebuild-registry.sh
```

---

## FAZA 9 — Înregistrare în routing-table.yaml (dacă domeniu nou)

**Fișier**: `~/.nexus/config/routing-table.yaml`

Dacă agentul introduce un domeniu nou (nu acoperit deja), adaugă în secțiunea `routes:`:

```yaml
  {new_domain}:
    primary_agent: {agent_lower}
    model: "claude-sonnet-4-6"
    fallback_agent: genie
    timeout_s: 1800
    complexity_override:
      low: { model: "claude-haiku-4-5-20251001", timeout_s: 600 }
      medium: { model: "claude-sonnet-4-6", timeout_s: 1800 }
      high: { model: "claude-sonnet-4-6", timeout_s: 2700 }
```

Adaugă și în `block_keywords:`:
```yaml
  "/{agent_lower}": {agent_lower}
```

Adaugă și în `agent_keywords:`:
```yaml
  {agent_lower}: [{keyword-1}, {keyword-2}, {keyword-3}]
```

Adaugă și în `classification_rules:`:
```yaml
  - domain: {new_domain}
    keywords: [{keyword-1}, {keyword-2}, {keyword-3}, ...]
```

---

## FAZA 10 — Configurare heartbeat (DOAR dacă agentul are heartbeat periodic)

**Sari această fază complet dacă agentul este event-driven (heartbeat_freq_min: 0).**

### 10a. Creare heartbeat.sh

Copiază template de la un agent similar:
```bash
cp ~/.nexus/agents/iris/scripts/heartbeat.sh \
   ~/.nexus/agents/{agent_lower}/scripts/heartbeat.sh
chmod +x ~/.nexus/agents/{agent_lower}/scripts/heartbeat.sh
```

Editează variabilele din script:
- `AGENT_DIR` → `$HOME/.nexus/agents/{agent_lower}`
- `LOCK_FILE` → `/tmp/nexus-{agent_lower}-heartbeat.lock`
- `LOG_FILE` → `$LOG_DIR/{agent_lower}-heartbeat.log`
- Model Claude în comanda de invoke → cel specificat în HEARTBEAT.md
- `HEARTBEAT_TIMEOUT_S` → timeout adecvat (ex: 240 pentru agenți simpli, 720 pentru research)
- `HEARTBEAT_MAX_TURNS` → număr de turns LLM (ex: 6-20)

### 10b. Creare LaunchAgent plist

**Calculează offset** pentru a evita coliziunile:
- GENIE: minute 0, 30 → liber: minute 10, 20, 40, 50
- IRIS: minute 20 → deja ocupat
- Agent nou cu 30min frecvență → alege minute 10 sau 40
- Agent nou cu 60min frecvență → alege minute 50

**Fișier**: `~/Library/LaunchAgents/com.nexus.{agent_lower}-heartbeat.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nexus.{agent_lower}-heartbeat</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/pafi/.nexus/agents/{agent_lower}/scripts/heartbeat.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <!-- Pentru 30min (minute 10 și 40): -->
    <array>
        <dict><key>Minute</key><integer>10</integer></dict>
        <dict><key>Minute</key><integer>40</integer></dict>
    </array>
    <!-- SAU pentru 60min (minute 50): -->
    <!-- <dict><key>Minute</key><integer>50</integer></dict> -->
    <key>StandardOutPath</key>
    <string>/Users/pafi/.nexus/logs/{agent_lower}-heartbeat.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/pafi/.nexus/logs/{agent_lower}-heartbeat.err.log</string>
    <key>RunAtLoad</key>
    <true/>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/pafi/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>HOME</key>
        <string>/Users/pafi</string>
    </dict>
</dict>
</plist>
```

### 10c. Încarcare LaunchAgent

```bash
launchctl load ~/Library/LaunchAgents/com.nexus.{agent_lower}-heartbeat.plist
```

Verificare că s-a încărcat:
```bash
launchctl list | grep {agent_lower}
```

---

## FAZA 11 — Update GENIE HEARTBEAT.md (Step 1)

**Fișier**: `~/.nexus/agents/genie/HEARTBEAT.md`

Adaugă agentul nou în **Step 1** (lista de PROGRESS.md monitorizate):

```markdown
### Step 1: Citeste PROGRESS.md toti agentii
- Read: ~/.nexus/agents/mercury/PROGRESS.md
- Read: ~/.nexus/agents/iris/PROGRESS.md
- Read: ~/.nexus/agents/sentinel/PROGRESS.md
- Read: ~/.nexus/agents/tech/PROGRESS.md
- Read: ~/.nexus/agents/{agent_lower}/PROGRESS.md    ← ADAUGĂ ACEASTĂ LINIE
```

---

## FAZA 12 — Smoke Test

### Test 1: Structura de fișiere

```bash
AGENT_LOWER="{agent_lower}"
AGENT_DIR="$HOME/.nexus/agents/$AGENT_LOWER"

echo "=== Smoke Test: $AGENT_LOWER ==="

# Verificare fișiere obligatorii
for f in SOUL.md AGENTS.md IDENTITY.md HEARTBEAT.md MEMORY.md \
          PROGRESS.md DISPATCH.md TOOLS.md tools.yaml skills.yaml; do
    if [ -f "$AGENT_DIR/$f" ]; then
        echo "OK  $f"
    else
        echo "FAIL  $f LIPSĂ"
    fi
done

# Verificare workspace
for d in workspace/current-task workspace/output; do
    if [ -d "$AGENT_DIR/$d" ]; then
        echo "OK  $d/"
    else
        echo "FAIL  $d/ LIPSĂ"
    fi
done
```

### Test 2: agent-registry.yaml conține agentul

```bash
grep -q "{agent_lower}" ~/.nexus/config/agent-registry.yaml \
    && echo "OK  agent-registry.yaml: agent înregistrat" \
    || echo "FAIL  agent-registry.yaml: agent NU găsit"
```

### Test 3: routing-table.yaml (dacă domeniu nou)

```bash
grep -q "{new_domain}" ~/.nexus/config/routing-table.yaml \
    && echo "OK  routing-table.yaml: domeniu înregistrat" \
    || echo "FAIL  routing-table.yaml: domeniu NU găsit"
```

### Test 4: PROGRESS.md are format corect

```bash
python3 -c "
import re, sys
content = open('$HOME/.nexus/agents/{agent_lower}/PROGRESS.md').read()
required = ['msg_type', 'status', 'agent', 'timestamp', 'spent_usd']
missing = [f for f in required if f not in content]
if missing:
    print('FAIL  PROGRESS.md: câmpuri lipsă:', missing)
    sys.exit(1)
print('OK  PROGRESS.md: format valid')
"
```

### Test 5: SOUL.md are secțiunile obligatorii

```bash
python3 -c "
content = open('$HOME/.nexus/agents/{agent_lower}/SOUL.md').read()
required = ['## Core Identity', '## Your Role', '## Autonomy', '## Hard Boundaries', '## Trust Levels']
missing = [s for s in required if s not in content]
if missing:
    print('FAIL  SOUL.md: secțiuni lipsă:', missing)
else:
    print('OK  SOUL.md: toate secțiunile prezente')
"
```

### Test 6: LaunchAgent (dacă agent cu heartbeat)

```bash
launchctl list | grep "com.nexus.{agent_lower}-heartbeat" \
    && echo "OK  LaunchAgent: activ" \
    || echo "FAIL  LaunchAgent: NU găsit (sau event-driven — skip OK)"
```

### Test 7: GENIE vede agentul nou

```bash
grep -q "{agent_lower}" ~/.nexus/agents/genie/HEARTBEAT.md \
    && echo "OK  GENIE HEARTBEAT.md: agent inclus în monitoring" \
    || echo "WARN  GENIE HEARTBEAT.md: agent NU menționat (adaugă manual dacă e necesar)"
```

### Test 8: Task de test simplu (manual)

Dacă agentul este event-driven, trimite un task de test minimal:

```bash
# Creează task de test
cat > ~/.nexus/agents/{agent_lower}/workspace/current-task/task.md << 'EOF'
---
task_id: "smoke-test-001"
priority: LOW
domain: {domain}
complexity: DIRECT
description: "Smoke test: confirmă că agentul poate citi task-ul și scrie output."
acceptance_criteria:
  - "Agentul citește task.md"
  - "Agentul scrie un fișier de output în workspace/output/"
deadline: null
input_files: []
EOF

echo "Task smoke test creat. Rulează agentul manual și verifică output."
```

---

## FAZA 13 — Actualizare documentație și MEMORY

### 13a. Actualizare LAUNCHAGENT-REGISTRY.md (dacă agent cu heartbeat)

**Fișier**: `~/.nexus/LAUNCHAGENT-REGISTRY.md`

Adaugă în secțiunea relevantă și în tabelul **Schedule Overview**.

### 13b. Salvare în Cortex

```
cortex_store(
  key: "nexus-agent-onboarding-{AGENT_NAME}-{YYYY-MM-DD}",
  content: "Agent {AGENT_NAME} adăugat în NexusOS. Tip: {type}. Domeniu: {domain}. Heartbeat: {freq}min. Files: SOUL.md, AGENTS.md, IDENTITY.md, HEARTBEAT.md, skills.yaml, tools.yaml, PROGRESS.md, DISPATCH.md. Registry: agent-registry.yaml. Smoke test: PASS.",
  tags: ["nexus", "agent-onboarding", "{agent_lower}", "infrastructure"]
)
```

### 13c. Update MEMORY.md (via propunere GENIE)

Propune adăugarea în MEMORY.md a secțiunii despre noul agent:
- Rol în arhitectură
- Cu ce agenți interacționează
- Orice preferință specială de routing

---

## CHECKLIST FINAL

```
[ ] Faza 1: Directoare create
[ ] Faza 2: SOUL.md creat cu toate secțiunile (Core Identity, Role, Relationships, Autonomy, Hard Boundaries, Trust Levels, Skills)
[ ] Faza 3: AGENTS.md creat cu workflow complet și quality gates
[ ] Faza 4: IDENTITY.md creat (self-description scurtă)
[ ] Faza 5: HEARTBEAT.md creat (event-driven sau cu pași heartbeat)
[ ] Faza 6: PROGRESS.md și DISPATCH.md create cu format NEXUS-MESSAGING-PROTOCOL
[ ] Faza 6: MEMORY.md creat (gol la inițializare)
[ ] Faza 7: skills.yaml și tools.yaml create
[ ] Faza 8: agent-registry.yaml actualizat (bloc agent + capability_index)
[ ] Faza 9: routing-table.yaml actualizat (dacă domeniu nou)
[ ] Faza 10: heartbeat.sh + LaunchAgent create și încărcate (SKIP dacă event-driven)
[ ] Faza 11: GENIE HEARTBEAT.md actualizat (Step 1)
[ ] Faza 12: Smoke test PASS (toate 7 teste OK, sau justificat SKIP)
[ ] Faza 13: Cortex saved, MEMORY.md propunere trimisă la GENIE
```

---

## Referințe rapide — structuri existente de copiat

| Agent | Tip | Heartbeat | Model de copiat pentru |
|-------|-----|-----------|----------------------|
| MERCURY | worker | event-driven | Workers fără heartbeat periodic |
| IRIS | worker | 60min | Workers cu heartbeat și research |
| GENIE | orchestrator | 30min | Orchestratori cu heartbeat complex |
| SENTINEL | service | 10min (pur bash) | Service-uri fără LLM |
| TECH | worker | event-driven | Workers tehnici fără heartbeat |

**Cale directoare de referință**: `~/.nexus/agents/{mercury|iris|genie|sentinel|tech}/`
