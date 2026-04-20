---
name: tailscale-logout-recovery
description: Use when SSH/SCP fails after Tailscale logout — step-by-step recovery with exact commands
---

# Tailscale Logged Out -- SSH/SCP Esueaza

**Status**: ACTIVE
**Creat**: 2026-02-28
**Versiune**: 1.0
**Regula asociata**: OPS-H-001
**Scope**: Rezolvarea situatiei in care Tailscale e delogat pe MacIntel si SSH/SCP la adrese 100.x.x.x esueaza.

## 1. Problema

Tailscale se poate deloga silentios pe MacIntel. Orice SSH/SCP la adrese Tailscale (100.x.x.x) esueaza.
- tailscale status returneaza: Logged out.
- SCP la MacM4 (100.67.181.56) esueaza
- SSH la VPS via Tailscale (100.81.233.9) esueaza

## 2. Procedura

Pas 1: tailscale status -- daca = Logged out, continua.
Pas 2: tailscale up -- reconecteaza fara browser daca sesiunea e valida.
Pas 3: tailscale status -- device-urile apar cu IP. Test: ssh pafi@100.67.181.56 'echo OK'

## 3. Cortex Logging

Salvat automat la sesiune via Post-H gate.

## 4. Enforcement Loop

WHERE: Orice eroare SSH/SCP pe adrese 100.x.x.x
WHEN: La fiecare Connection refused pe Tailscale
HOW: Verifica tailscale status INAINTE de alte cauze
CONNECT: OPS-H-001, procedure-health.json
VERIFY: tailscale status OK + SSH test OK

VK1: [PROC] FORGE | p1+ p2+ p3+ p4+ VER+ | complete
VK2: [CORTEX] Tailscale Logged Out Fix | FORGE+ | rule: OPS-H-001 | v1.0
