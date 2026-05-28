"""
_oauth.py -- OAuth credential loaders for /council provider auth.

Pafi's environment uses OAuth only (no API keys for Anthropic/OpenAI).
This module centralizes credential retrieval with fail-closed defaults.

Anthropic: macOS keychain "Claude Code-credentials" → ~/.claude/.credentials.json → ANTHROPIC_API_KEY env
OpenAI/GPT-5.5: ~/.codex/auth.json consumed by `codex exec` CLI (no direct load needed)
Gemini: GEMINI_API_KEY / GOOGLE_API_KEY env (no OAuth)
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import subprocess
import time
from typing import Optional


class OAuthLoadError(Exception):
    """Raised when OAuth credential cannot be loaded for a provider."""


def load_anthropic_oauth_token() -> str:
    """
    Load Anthropic OAuth token from macOS keychain "Claude Code-credentials",
    fall back to ~/.claude/.credentials.json, then fall back to ANTHROPIC_API_KEY env.

    v1.0.3 IMPORTANT: The token returned here is subscription-scoped
    (sk-ant-oat01-...), NOT API-scoped. It MUST NOT be passed to
    anthropic.Anthropic(auth_token=...).messages.create() — that returns 401.

    The ONLY valid use of this token is via the `claude` CLI subprocess, which
    reads the keychain internally. This function is now primarily useful for
    diagnostics (checking that credentials exist) and is called by
    _call_claude_subprocess implicitly via the CLI's own keychain access.

    Use _call_claude_subprocess() (in _providers.py) for all Anthropic calls.

    Returns the token string if found (useful for diagnostics/debug).
    Raises OAuthLoadError if no credential path succeeds.
    """
    # 1. macOS keychain
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            raw = result.stdout.strip()
            try:
                creds = json.loads(raw)
                # Claude Code 2026.5 keychain shape: {"claudeAiOauth":{"accessToken":...}}
                # Legacy shapes also tried for compatibility.
                token = (
                    creds.get("claudeAiOauth", {}).get("accessToken")
                    or creds.get("tokens", {}).get("access_token")
                    or creds.get("access_token")
                )
                if token:
                    return token
            except json.JSONDecodeError:
                # raw may BE the token (bare string, not JSON)
                if raw and len(raw) > 20:
                    return raw
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 2. Fallback file ~/.claude/.credentials.json
    creds_file = pathlib.Path.home() / ".claude" / ".credentials.json"
    if creds_file.exists():
        try:
            creds = json.loads(creds_file.read_text(encoding="utf-8"))
            token = (
                creds.get("claudeAiOauth", {}).get("accessToken")
                or creds.get("tokens", {}).get("access_token")
                or creds.get("access_token")
            )
            if token:
                return token
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Env-var fallback (legacy support / CI environments)
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key

    raise OAuthLoadError(
        "anthropic: no OAuth token found. Tried keychain 'Claude Code-credentials', "
        "~/.claude/.credentials.json, and ANTHROPIC_API_KEY env. "
        "Run `claude setup-token` to refresh."
    )


def codex_auth_present() -> bool:
    """Return True if ~/.codex/auth.json exists and is non-empty (>10 bytes)."""
    auth_file = pathlib.Path.home() / ".codex" / "auth.json"
    return auth_file.exists() and auth_file.stat().st_size > 10


def codex_token_age_seconds() -> Optional[float]:
    """
    Return the age in seconds of the Codex auth token's JWT exp claim,
    or None if the file is missing, unreadable, or not a valid JWT.

    A positive value means the token has already expired (time.time() - exp > 0).
    A negative value means the token is still valid.
    """
    auth_file = pathlib.Path.home() / ".codex" / "auth.json"
    if not auth_file.exists():
        return None
    try:
        data = json.loads(auth_file.read_text(encoding="utf-8"))
        token = (
            data.get("tokens", {}).get("access_token")
            or data.get("access_token")
        )
        if not token:
            return None
        # JWT: header.payload.signature — decode payload without verifying signature
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # Pad to multiple of 4 for base64 decode
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(padded))
        exp = decoded.get("exp")
        if exp is not None:
            return float(time.time()) - float(exp)
        return None
    except Exception:
        return None


def load_gemini_api_key() -> str:
    """
    Load Gemini API key from environment. No OAuth path for Gemini in 2026.5.

    Raises OAuthLoadError if neither GEMINI_API_KEY nor GOOGLE_API_KEY is set.
    """
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise OAuthLoadError(
            "gemini: no API key in env. Set GEMINI_API_KEY in ~/.zshrc."
        )
    return key
