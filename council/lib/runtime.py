"""
runtime.py -- Runtime-aware support-model routing for /council.

Advisor lanes stay fixed:
  - Ollama Cloud GLM 5.2
  - Claude Opus 4.8
  - GPT-5.5

Non-advisor support steps use the host runtime's native model:
  - Codex/.agents -> GPT-5.5 via Codex OAuth
  - Claude Code   -> Claude Opus 4.8 via Claude CLI/OAuth

Override with COUNCIL_SUPPORT_PROVIDER when an operator needs an explicit
provider key.
"""

from __future__ import annotations

import os
from pathlib import Path


def runtime_name() -> str:
    """Infer the active runtime from the installed skill path."""
    override = os.environ.get("COUNCIL_RUNTIME")
    if override:
        return override

    parts = set(Path(__file__).resolve().parts)
    if ".claude" in parts:
        return "claude-code"
    if ".codex" in parts:
        return "codex"
    if ".agents" in parts:
        return "codex"
    return "codex"


def support_provider_key() -> str:
    """Return the provider key for non-advisor support calls."""
    override = os.environ.get("COUNCIL_SUPPORT_PROVIDER")
    if override:
        return override
    if runtime_name() == "claude-code":
        return "opus-4-8"
    return "gpt-5.5"


def support_provider_label() -> str:
    """Human-readable label for ledgers and reports."""
    return support_provider_key()
