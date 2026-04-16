---
name: openai-codex-account-expiry-reminder
description: Reminder: contul OpenAI Codex (cryptopafi@gmail.com) expiră pe 19 aprilie
---

Trimite un reminder urgent lui Pafi:

⚠️ REMINDER: Contul OpenAI Codex (cryptopafi@gmail.com) folosit pentru gpt-5.4 în OpenClaw și Hermes **expiră MÂINE, pe 19 Aprilie**.

Trebuie să:
1. Creezi un cont nou OpenAI / obții un nou token Codex
2. Rulezi `openclaw models auth login --provider openai-codex` cu noul cont
3. Actualizezi Hermes auth.json cu noile credențiale

Fișiere de actualizat după cont nou:
- `~/.openclaw/agents/main/agent/auth-profiles.json`
- `~/.openclaw/openclaw.json` (auth.profiles)
- `~/.hermes/auth.json` (providers.openai-codex.tokens)

Spune-i lui Pafi că Genie e gata să facă switch-ul imediat ce are noul cont.