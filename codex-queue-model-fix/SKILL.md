---
name: codex-queue-model-fix
description: "Codex queue model fix: dacă taskurile apar DONE imediat cu duration=1s și eroare JSON in logs, modelul specificat în **Model**: field nu există."
---

Codex queue model fix: dacă taskurile apar DONE imediat cu duration=1s și eroare JSON in logs, modelul specificat în **Model**: field nu există. Modele disponibile Codex: gpt-5.3-codex (current), gpt-5.2-codex, gpt-5.1-codex-max, gpt-5.2, gpt-5.1-codex-mini. gpt-4.1 NU există. Fix: python3 replace all **Model**: gpt-4.1 cu gpt-5.3-codex, re-mark Status DONE -> PENDING.
