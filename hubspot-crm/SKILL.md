---
name: hubspot-crm
description: "Operate HubSpot CRM from bash for contacts, deals, searches, stale pipeline checks, and notes"
---

Operate HubSpot CRM from bash for contacts, deals, searches, stale pipeline checks, and notes

# HubSpot CRM Skill

## Purpose
Run common HubSpot CRM actions from terminal with no Python/Node runtime dependencies.

## Script
`/Users/pafi/.claude/projects/-Users-pafi/memory/scripts/hubspot.sh`

## Auth
1. Preferred: keep token in Keychain.
```bash
security add-generic-password -U -s "hubspot" -a "api-key" -w "<HUBSPOT_PRIVATE_APP_TOKEN>"
```
2. Optional session override:
```bash
export HUBSPOT_API_KEY="<HUBSPOT_PRIVATE_APP_TOKEN>"
```
3. Load functions:
```bash
source /Users/pafi/.claude/p
