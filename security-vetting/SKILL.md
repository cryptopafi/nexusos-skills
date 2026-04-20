---
name: security-vetting
description: "Run 14-point security checklist before installing skills or MCP servers"
---

Run 14-point security checklist before installing skills or MCP servers

# Security Vetting

## Purpose
Reduce riscul operational la instalari de skill-uri si MCP servere.

## Instructions
1. Ruleaza checklist complet inainte de instalare:
   1) source reputabil
   2) code review fara `eval/exec` dubios
   3) permissions explicite
   4) network calls documentate
   5) secrets doar din env
   6) data scope least privilege
   7) dependencies pinuite + audit
   8) prima rulare in sandbox
   9) checksum pentru binare
   10) single-purpose design
   11) update policy cont
