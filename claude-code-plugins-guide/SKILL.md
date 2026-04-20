---
name: claude-code-plugins-guide
description: Use when building or deploying a Claude Code plugin from first principles — covers structure and use
---

TOPIC: Claude Code Plugins — cum se construiesc și când se folosesc

CE SUNT: Pachete distribuite care extind Claude Code cu skills, agents, hooks, MCP servers. Disponibil din Claude Code 1.0.33+.

STRUCTURA:
```
plugin-name/
├── .claude-plugin/plugin.json   ← manifest (name, version, description)
├── skills/skill-name/SKILL.md   ← auto-invocate pe context
├── commands/cmd-name/           ← slash commands (/plugin:cmd)
├── agents/agent-name/           ← subagenti specializati
├── hooks/hooks.json             ← SessionStart/PreToolUse/PostToolUse/Stop
└── .mcp.json                    ← MCP servers
```

SKILLS vs COMMANDS:
- Skills = SKILL.md, auto-invocate de Claude când contextul se potrivește
- Commands = markdown în commands/, declanșate manual cu /plugin:name
- Skills budget: ~16.000 chars (2% context window) — dacă depășești, se exclud silențios

HOOKS DISPONIBILE:
- SessionStart (matcher: startup/resume/clear/compact) — stdout injectat în context
- PreToolUse — rulează înainte de tool
- PostToolUse (matcher: regex pe tool name) — rulează după tool
- Stop — rulează la exit
- Hooks sunt async opțional. Timeout default 600s — SETEAZĂ timeout explicit!

INSTALARE SI TEST:
- Test local: claude --plugin-dir ./my-plugin
- Multiple: claude --plugin-dir ./p1 --plugin-dir ./p2
- Distributie: marketplace via /plugin install

CÂND SĂ FOLOSEȘTI PLUGIN vs STANDALONE:
- Standalone (.claude/): proiect single, experiment rapid, skill names scurte
- Plugin: sharing cu echipă, multiple proiecte, versioning, marketplace

REGULĂ ARHITECTURALĂ (Opus audit 2026-02-26):
- NU duplica în plugin ce există deja în CLAUDE.md
- Pluginurile sunt pentru funcționalitate NOU care nu poate fi exprimată în CLAUDE.md
- PostToolUse pe Bash|Edit|Write = 250+ fire/sesiune = overhead inacceptabil
- SessionStart hook cu curl = util DAR setează timeout 5s + fallback local
- Stop hook cu Haiku prompt = bun pentru procedure scan la exit

ALTERNATIVA PREFERATĂ față de plugin complex:
2 hooks standalone în ~/.claude/settings.json:
1. SessionStart → curl Cortex top-5 proceduri (timeout 5s, fallback {})
2. Stop → Haiku prompt scan transcript pentru proceduri nesalvate
