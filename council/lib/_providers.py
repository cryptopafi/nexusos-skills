"""
_providers.py -- Shared provider adapters for the /council skill pipeline.

v1.0.3: Anthropic via `claude` CLI subprocess.

OAuth token (sk-ant-oat01-...) is subscription-scoped, NOT API-scoped.
Direct use of anthropic.Anthropic(auth_token=...).messages.create() returns
401. The `claude --print --output-format json --no-session-persistence` CLI
handles auth internally via macOS keychain — same pattern as codex exec for
OpenAI.

Anthropic advisor lane: subprocess → claude CLI (no SDK API calls)
OpenAI support lane + GPT advisor lane: subprocess → codex exec CLI
Gemini: env-key (GEMINI_API_KEY)

IMPORTANT: max_tokens and temperature are silently dropped for Anthropic calls.
The claude CLI determines these internally based on model + subscription.
A stderr warning is emitted if non-default values are passed so callers can
update their code.

Cost for Anthropic: total_cost_usd from claude CLI JSON is AUTHORITATIVE.
PROVIDER_REGISTRY prices are informational only for Anthropic entries.

Google SDK note: google.genai (google-genai package) is preferred. If not
available, falls back to google.generativeai (google-generativeai legacy).
On this installation google.generativeai is used (google.genai not present).
"""

from __future__ import annotations

import functools
import json as _json
import logging
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

from ._oauth import codex_auth_present  # noqa: F401 — module-level for monkeypatching

try:
    import google.genai as _google_genai_mod
    _GOOGLE_SDK = "genai"
except ImportError:
    import google.generativeai as _google_genai_mod  # type: ignore[no-redef]
    _GOOGLE_SDK = "generativeai"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class TransientProviderError(Exception):
    """Retryable error: timeout, 5xx, rate-limit."""

    def __init__(self, provider: str, msg: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {msg}")


class PermanentProviderError(Exception):
    """Non-retryable error: 4xx auth, schema fail, missing API key."""

    def __init__(self, provider: str, msg: str) -> None:
        self.provider = provider
        super().__init__(f"[{provider}] {msg}")


# ---------------------------------------------------------------------------
# Provider registry — price table (USD per token)
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "gpt-5.5-nano": {
        # Legacy key kept for old normalizer tests; routed to full GPT-5.5.
        "vendor": "openai",
        "model_id": "gpt-5.5",
        "price_in": 5.00 / 1e6,
        "price_out": 20.00 / 1e6,
    },
    "gemini-2.5-flash": {
        "vendor": "google",
        "model_id": "gemini-2.5-flash",
        "price_in": 0.35 / 1e6,
        "price_out": 1.05 / 1e6,
    },
    # --- Legacy utility aliases kept for older tests/codepaths ---
    # Runtime support routing must still go through OpenAI/Codex GPT-5.5.
    # Do not point these aliases at Haiku/Sonnet/Gemini unless advisor lanes
    # explicitly require it.
    "sonnet-4-6": {
        "vendor": "openai",
        "model_id": "gpt-5.5",
        "price_in": 5.00 / 1e6,
        "price_out": 20.00 / 1e6,
    },
    "haiku-4-5": {
        "vendor": "openai",
        "model_id": "gpt-5.5",
        "price_in": 5.00 / 1e6,
        "price_out": 20.00 / 1e6,
    },
    # --- Advisor lane models (Tasks 4-6, max-reasoning) ---
    "gemini-3.1-pro": {
        "vendor": "google",
        "model_id": "gemini-3-pro-preview",
        "price_in": 3.50 / 1e6,
        "price_out": 14.00 / 1e6,
    },
    "opus-4-8": {
        "vendor": "anthropic",
        "model_id": "claude-opus-4-8",
        "price_in": 5.00 / 1e6,
        "price_out": 25.00 / 1e6,
    },
    "gpt-5.5": {
        "vendor": "openai",
        "model_id": "gpt-5.5",
        "price_in": 5.00 / 1e6,
        "price_out": 20.00 / 1e6,
    },
    "ollama-glm-5.2-cloud": {
        "vendor": "ollama",
        "model_id": "glm-5.2:cloud",
        # Ollama cloud pricing is account-side; keep local meter conservative
        # until the API returns billable usage in a stable field.
        "price_in": 0.00,
        "price_out": 0.00,
    },
    "deepseek-v4-pro": {
        "vendor": "deepseek",
        "model_id": "deepseek-v4-pro",
        # Official DeepSeek V4-Pro pricing, cache-miss input + output.
        "price_in": 0.435 / 1e6,
        "price_out": 0.87 / 1e6,
    },
}


# ---------------------------------------------------------------------------
# Cached client factories
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _get_anthropic_client() -> None:
    """
    v1.0.3: returns None — Anthropic SDK no longer used for API calls.

    OAuth token (sk-ant-oat01-...) is subscription-scoped, not API-scoped.
    Direct SDK use returns 401. All Anthropic calls now go through
    _call_claude_subprocess() which uses the `claude` CLI internally.

    Kept as @lru_cache pass-through for backwards compat with tests that
    monkeypatch _get_anthropic_client. Verifies claude CLI is available;
    raises PermanentProviderError if not installed.

    Returns None — no client object is constructed.
    """
    if not shutil.which("claude"):
        raise PermanentProviderError(
            "anthropic",
            "claude CLI not installed; OAuth path requires CLI. "
            "Install via: curl -fsSL https://claude.ai/install.sh | bash",
        )
    return None


def _get_openai_client() -> None:
    """
    OpenAI SDK path is disabled for /council.

    All OpenAI calls use _call_codex_subprocess() so Codex OAuth is the single
    runtime auth surface. This includes support steps (triage, normalize,
    anonymize, reconcile) and the GPT-5.5 advisor lane.
    """
    raise PermanentProviderError(
        "openai",
        "OpenAI SDK path disabled — /council uses `codex exec` subprocess "
        "for all GPT-5.5 calls via Codex OAuth.",
    )


@functools.lru_cache(maxsize=1)
def _get_gemini_client() -> Any:
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise PermanentProviderError("gemini", "missing GEMINI_API_KEY")
    if _GOOGLE_SDK == "genai":
        return _google_genai_mod.Client(api_key=api_key)
    else:
        _google_genai_mod.configure(api_key=api_key)
        return _google_genai_mod


# ---------------------------------------------------------------------------
# Unified call interface
# ---------------------------------------------------------------------------

def call_provider(
    provider: str,
    system: str,
    user: str,
    *,
    max_tokens: int = 2048,
    temperature: float = 0.2,
    timeout_s: float = 180.0,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    """
    Unified call interface across Anthropic, OpenAI, and Google.

    Args:
        provider:         One of the keys in PROVIDER_REGISTRY.
        system:           System prompt text.
        user:             User message text.
        max_tokens:       Maximum output tokens.
        temperature:      Sampling temperature.
        timeout_s:        Request timeout in seconds.
        **provider_kwargs: Optional model-specific kwargs for future use
                          (e.g. thinking_level, reasoning.effort for
                          max-reasoning models in Tasks 4-6).

    Returns:
        {"text": str, "tokens": {"in": int, "out": int}}

    Raises:
        TransientProviderError: on retryable failures (timeout, 5xx, rate-limit).
        PermanentProviderError: on non-retryable failures (4xx auth, bad key,
                                unknown provider).
    """
    if provider not in PROVIDER_REGISTRY:
        raise PermanentProviderError(provider, f"unknown provider {provider!r}")

    entry = PROVIDER_REGISTRY[provider]
    vendor: str = entry["vendor"]
    model_id: str = entry["model_id"]

    if vendor == "anthropic":
        return _call_anthropic(provider, model_id, system, user, max_tokens, temperature, timeout_s, **provider_kwargs)
    elif vendor == "openai":
        return _call_openai(provider, model_id, system, user, max_tokens, temperature, timeout_s, **provider_kwargs)
    elif vendor == "google":
        return _call_google(provider, model_id, system, user, max_tokens, temperature, timeout_s, **provider_kwargs)
    elif vendor == "ollama":
        return _call_ollama(provider, model_id, system, user, max_tokens, temperature, timeout_s, **provider_kwargs)
    elif vendor == "deepseek":
        return _call_deepseek(provider, model_id, system, user, max_tokens, temperature, timeout_s, **provider_kwargs)
    else:
        raise PermanentProviderError(provider, f"unsupported vendor {vendor!r}")


# ---------------------------------------------------------------------------
# Vendor-specific implementations
# ---------------------------------------------------------------------------

def _call_claude_subprocess(
    *,
    model: str,
    system: str,
    user: str,
    timeout_s: float = 180.0,
    max_budget_usd: float | None = None,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    """
    Call Anthropic via `claude --print --output-format json` CLI subprocess.

    v1.0.3: OAuth token handled internally by the CLI (reads macOS keychain
    "Claude Code-credentials"). No SDK API calls — the subscription-scoped
    OAuth token returns 401 against api.anthropic.com directly.

    Args:
        model:          Model id, e.g. "claude-haiku-4-5", "claude-sonnet-4-6".
        system:         System prompt text.
        user:           User message text.
        timeout_s:      Subprocess timeout in seconds.
        max_budget_usd: Optional spend cap forwarded as --max-budget-usd.
        **provider_kwargs: thinking= and other kwargs SILENTLY DROPPED —
                          claude CLI manages these internally.

    Returns:
        {
            "text": str,
            "tokens": {"in": int, "out": int,
                       "cache_read": int, "cache_creation": int},
            "cost_usd": float,   # AUTHORITATIVE for Anthropic (from CLI JSON)
            "duration_ms": int,
        }

    Raises:
        PermanentProviderError: CLI missing, 401/auth, model not found, non-JSON output.
        TransientProviderError: timeout, rate-limit signals, 5xx signals.

    Note: cost_usd is charged against the Max subscription budget, not an
    API account. This is correct for Pafi's setup (Max plan subscriber).
    """
    if not shutil.which("claude"):
        raise PermanentProviderError(
            "anthropic",
            "claude CLI not installed; install via: curl -fsSL https://claude.ai/install.sh | bash",
        )

    # Combine system + user with a clear delimiter so the model can distinguish them
    prompt = f"# System Instructions\n\n{system}\n\n# User Request\n\n{user}\n"

    # FIX-C2: warn if payload is large; content is passed via stdin (input=) to avoid
    # macOS ARG_MAX (~256KB) truncation. This is intentional — do NOT move to argv.
    payload_bytes = prompt.encode("utf-8")
    if len(payload_bytes) > 100_000:
        sys.stderr.write(
            f"[warn] brief payload {len(payload_bytes)} bytes — using stdin to avoid macOS argv limit\n"
        )

    cmd = [
        "claude", "--print", "--model", model,
        "--output-format", "json",
        "--no-session-persistence",
    ]
    if max_budget_usd is not None:
        cmd.extend(["--max-budget-usd", f"{max_budget_usd:.4f}"])

    try:
        # FIX-C2: content passed via stdin (input=prompt, text=True), NOT via argv.
        # This avoids macOS ARG_MAX (~256KB) truncation for large briefs.
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        raise TransientProviderError(
            "anthropic", f"claude CLI timed out after {timeout_s}s"
        )

    data = None
    if result.stdout:
        try:
            data, _ = _json.JSONDecoder().raw_decode(result.stdout.lstrip())
        except _json.JSONDecodeError:
            data = None

    if result.returncode != 0 and data is None:
        err = (result.stderr or "").lower()
        if "401" in err or "auth" in err or "credentials" in err or "login" in err:
            raise PermanentProviderError(
                "anthropic", f"claude CLI auth fail: {result.stderr[:200]}"
            )
        if "model not found" in err or "invalid model" in err or "404" in err:
            raise PermanentProviderError(
                "anthropic", f"claude CLI model error: {result.stderr[:200]}"
            )
        if "timeout" in err or "rate" in err or "503" in err or "502" in err or "504" in err:
            raise TransientProviderError(
                "anthropic", f"claude CLI transient: {result.stderr[:200]}"
            )
        raise PermanentProviderError(
            "anthropic", f"claude CLI error rc={result.returncode}: {result.stderr[:200]}"
        )

    # Parse JSON output
    if data is None:
        try:
            data, _ = _json.JSONDecoder().raw_decode(result.stdout.lstrip())
        except _json.JSONDecodeError:
            raise PermanentProviderError(
                "anthropic", f"claude CLI returned non-JSON: {result.stdout[:200]}"
            )

    if data.get("is_error"):
        api_err = data.get("api_error_status") or data.get("error") or "unknown"
        err_str = str(api_err).lower()
        if "429" in err_str or "rate" in err_str:
            raise TransientProviderError("anthropic", f"claude CLI rate-limit: {api_err}")
        if "401" in err_str or "auth" in err_str:
            raise PermanentProviderError("anthropic", f"claude CLI auth fail: {api_err}")
        raise PermanentProviderError("anthropic", f"claude CLI is_error: {api_err}")

    text = data.get("result", "")
    usage = data.get("usage") or {}

    return {
        "text": text,
        "tokens": {
            "in": int(usage.get("input_tokens", 0) or 0),
            "out": int(usage.get("output_tokens", 0) or 0),
            "cache_read": int(usage.get("cache_read_input_tokens", 0) or 0),
            "cache_creation": int(usage.get("cache_creation_input_tokens", 0) or 0),
        },
        "cost_usd": float(data.get("total_cost_usd", 0.0) or 0.0),
        "duration_ms": int(data.get("duration_ms", 0) or 0),
    }


def _call_anthropic(
    provider: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    """
    v1.0.3: route through claude CLI subprocess. SDK path deprecated.

    max_tokens, temperature, and provider_kwargs (thinking=, etc.) are
    SILENTLY DROPPED — claude CLI determines these internally based on model
    + subscription. A stderr warning is emitted when non-default values are
    passed so callers know to update their code.

    FIX-5 drift-guard (budget_tokens fallback) is dead code — the CLI handles
    model API drift internally. Removed.

    Backwards compat: signature unchanged from v1.0.2.
    """
    _DEFAULT_MAX_TOKENS = 16384
    _DEFAULT_TEMPERATURE = 1.0

    if max_tokens != _DEFAULT_MAX_TOKENS or temperature != _DEFAULT_TEMPERATURE:
        # FIX-M1: demoted from sys.stderr.write to logger.debug to suppress
        # the 29-line spam produced by the voice-normalizer's sequential Haiku calls.
        # Set LOG_LEVEL=DEBUG to see these messages.
        logger.debug(
            "[anthropic] v1.0.3: max_tokens=%r / temperature=%r dropped for %s "
            "(claude CLI manages these internally)",
            max_tokens, temperature, model_id,
        )

    result = _call_claude_subprocess(
        model=model_id,
        system=system,
        user=user,
        timeout_s=timeout_s,
        **provider_kwargs,
    )
    # Normalise to the minimal shape callers expect: text + tokens
    # cost_usd and duration_ms are bonus fields; callers may ignore them.
    return result


def _call_codex_subprocess(
    *,
    model: str,
    system: str,
    user: str,
    timeout_s: float = 240.0,
    reasoning_effort: str = "xhigh",
    verbosity: str = "high",
) -> dict[str, Any]:
    """
    Call GPT-5.5 via `codex exec` CLI subprocess.

    Auth is handled internally by the CLI reading ~/.codex/auth.json.
    No OPENAI_API_KEY is required.

    Args:
        model:            Model identifier, e.g. "gpt-5.5".
        system:           System prompt text.
        user:             User message text.
        timeout_s:        Subprocess timeout in seconds.
        reasoning_effort: Reasoning effort level (xhigh/high/medium/low).
        verbosity:        Text verbosity level (high/medium/low).

    Returns:
        {"text": str, "tokens": {"in": int, "out": int}}
        Token counts are estimated from char counts (codex CLI does not always
        emit token usage for raw-text output).

    Raises:
        PermanentProviderError: on 401/auth failure, missing CLI, missing auth.json.
        TransientProviderError: on subprocess timeout or transient 5xx.
    """
    if not codex_auth_present():
        raise PermanentProviderError(
            "openai",
            "codex auth.json missing or empty — run `codex login` to authenticate",
        )

    if not shutil.which("codex"):
        raise PermanentProviderError(
            "openai",
            "codex CLI not installed — run `npm i -g @openai/codex-cli`",
        )

    # Combine system + user into a single prompt with system as preamble
    prompt = f"## System\n{system}\n\n## User\n{user}\n"

    prompt_file: str | None = None
    output_file: str | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as pf:
            pf.write(prompt)
            prompt_file = pf.name

        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False
        ) as of:
            output_file = of.name

        cmd = [
            "codex", "exec",
            "--model", model,
            "--sandbox", "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
            "-o", output_file,
            "-c", f"reasoning.effort={reasoning_effort}",
            "-c", f"text.verbosity={verbosity}",
        ]

        with open(prompt_file, encoding="utf-8") as pf_in:
            result = subprocess.run(
                cmd,
                stdin=pf_in,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )

        if result.returncode != 0:
            err = result.stderr.lower()
            if "401" in err or "unauthorized" in err or "auth" in err or "login" in err:
                raise PermanentProviderError(
                    "openai",
                    f"codex auth failure (rc={result.returncode}): {result.stderr[:200]}",
                )
            raise PermanentProviderError(
                "openai",
                f"codex exec failed (rc={result.returncode}): {result.stderr[:200]}",
            )

        out_path = pathlib.Path(output_file)
        output = out_path.read_text(encoding="utf-8") if out_path.exists() and out_path.stat().st_size > 0 else result.stdout

        # Token estimation from char count (4 chars ≈ 1 token)
        tokens_in = max(1, len(prompt.encode("utf-8")) // 4)
        tokens_out = max(1, len(output) // 4)

        return {"text": output, "tokens": {"in": tokens_in, "out": tokens_out}}

    except subprocess.TimeoutExpired:
        raise TransientProviderError(
            "openai",
            f"codex exec timed out after {timeout_s}s",
        )
    finally:
        if prompt_file:
            pathlib.Path(prompt_file).unlink(missing_ok=True)
        if output_file:
            pathlib.Path(output_file).unlink(missing_ok=True)


def _call_openai(
    provider: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    """
    OpenAI provider adapter — v1.0.2 dual-path:

    All OpenAI provider calls route through _call_codex_subprocess() using
    Codex OAuth at ~/.codex/auth.json. This is intentional: /council must use
    GPT-5.5 for every non-advisor support step and for the GPT advisor lane.

    The _use_responses_api flag is accepted only as a backwards-compatible
    no-op signal from older advisor code.
    """
    provider_kwargs.pop("_use_responses_api", None)

    reasoning_kwarg = provider_kwargs.get("reasoning", {})
    text_kwarg = provider_kwargs.get("text", {})
    reasoning_effort = (
        reasoning_kwarg.get("effort", "high")
        if isinstance(reasoning_kwarg, dict)
        else "high"
    )
    verbosity = (
        text_kwarg.get("verbosity", "medium")
        if isinstance(text_kwarg, dict)
        else "medium"
    )

    return _call_codex_subprocess(
        model=model_id,
        system=system,
        user=user,
        timeout_s=timeout_s,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
    )


def _post_json(
    *,
    provider: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
) -> dict[str, Any]:
    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout_s,
        )
    except requests.Timeout as exc:
        raise TransientProviderError(provider, f"request timed out after {timeout_s}s") from exc
    except requests.RequestException as exc:
        raise TransientProviderError(provider, f"request failed: {exc}") from exc

    text = response.text[:500]
    if response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        raise TransientProviderError(
            provider,
            f"HTTP {response.status_code}: {text}",
        )
    if response.status_code in {401, 403}:
        raise PermanentProviderError(
            provider,
            f"auth failed HTTP {response.status_code}: {text}",
        )
    if response.status_code >= 400:
        raise PermanentProviderError(
            provider,
            f"HTTP {response.status_code}: {text}",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise PermanentProviderError(provider, f"non-JSON response: {text}") from exc


def _estimate_tokens(*parts: str) -> dict[str, int]:
    prompt = "\n".join(parts)
    return {"in": max(1, len(prompt.encode("utf-8")) // 4), "out": 0}


def _env_or_keychain(service: str) -> str | None:
    value = os.environ.get(service)
    if value:
        return value
    security = shutil.which("security")
    if not security:
        return None
    try:
        result = subprocess.run(
            [security, "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    secret = (result.stdout or "").strip()
    return secret or None


def _call_ollama(
    provider: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    api_key = _env_or_keychain("OLLAMA_API_KEY")
    base_url = os.environ.get("OLLAMA_BASE_URL", "https://ollama.com").rstrip("/") + "/"
    if base_url.startswith("https://ollama.com") and not api_key:
        raise PermanentProviderError(
            provider,
            "missing OLLAMA_API_KEY for Ollama Cloud fallback",
        )

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    options: dict[str, Any] = {
        "temperature": temperature,
        # GLM reasoning models can spend the first small budget on internal
        # thinking and return an empty final content field. Keep a small floor
        # so smoke calls and fallback advisor calls get a final answer.
        "num_predict": max(int(max_tokens), 256),
    }
    if isinstance(provider_kwargs.get("options"), dict):
        options.update(provider_kwargs["options"])

    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": options,
    }
    data = _post_json(
        provider=provider,
        url=urljoin(base_url, "api/chat"),
        headers=headers,
        payload=payload,
        timeout_s=timeout_s,
    )
    message = data.get("message") or {}
    text = message.get("content") if isinstance(message, dict) else None
    if not text:
        raise PermanentProviderError(provider, "Ollama response missing message.content")
    tokens = {
        "in": int(data.get("prompt_eval_count", 0) or _estimate_tokens(system, user)["in"]),
        "out": int(data.get("eval_count", 0) or max(1, len(str(text).encode("utf-8")) // 4)),
    }
    return {"text": str(text), "tokens": tokens}


def _call_deepseek(
    provider: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    api_key = _env_or_keychain("DEEPSEEK_API_KEY")
    if not api_key:
        raise PermanentProviderError(provider, "missing DEEPSEEK_API_KEY")

    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/") + "/"
    payload: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    thinking = provider_kwargs.get("thinking")
    if isinstance(thinking, dict):
        payload["thinking"] = thinking
    data = _post_json(
        provider=provider,
        url=urljoin(base_url, "chat/completions"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        payload=payload,
        timeout_s=timeout_s,
    )
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        raise PermanentProviderError(provider, "DeepSeek response missing choices")
    message = choices[0].get("message") or {}
    text = message.get("content") if isinstance(message, dict) else None
    if not text:
        raise PermanentProviderError(provider, "DeepSeek response missing message.content")
    usage = data.get("usage") or {}
    tokens = {
        "in": int(usage.get("prompt_tokens", 0) or _estimate_tokens(system, user)["in"]),
        "out": int(usage.get("completion_tokens", 0) or max(1, len(str(text).encode("utf-8")) // 4)),
    }
    return {"text": str(text), "tokens": tokens}



def _classify_google_error(exc: Exception) -> tuple[str, str]:
    """Classify a Google SDK exception as ('transient'|'permanent', msg).

    Typed check from google.api_core.exceptions runs FIRST.
    String-match fallback runs LAST (covers non-API exceptions or missing import).
    """
    try:
        from google.api_core import exceptions as gax
        transient_types = (
            gax.DeadlineExceeded, gax.ResourceExhausted,
            gax.ServiceUnavailable, gax.InternalServerError,
            gax.GatewayTimeout,
        )
        permanent_types = (
            gax.Unauthenticated, gax.PermissionDenied,
            gax.NotFound, gax.InvalidArgument,
            gax.FailedPrecondition,
        )
        if isinstance(exc, transient_types):
            return ("transient", str(exc))
        if isinstance(exc, permanent_types):
            return ("permanent", str(exc))
    except ImportError:
        pass
    # String-match fallback for non-API exceptions or ImportError
    msg = str(exc).lower()
    if any(k in msg for k in ("timeout", "deadline", "timed out")):
        return ("transient", str(exc))
    if any(k in msg for k in ("quota", "429", "503", "504")):
        return ("transient", str(exc))
    if any(k in msg for k in ("500", "502", "internal")):
        return ("transient", str(exc))
    if any(k in msg for k in ("unauthenticated", "api key", "invalid key", "401", "403", "permission")):
        return ("permanent", str(exc))
    return ("permanent", f"unexpected_internal: {type(exc).__name__}: {exc}")


def _call_gemini_subprocess(
    *,
    model: str,
    system: str,
    user: str,
    timeout_s: float = 180.0,
) -> dict[str, Any]:
    """v1.0.4: Call Gemini via gemini-cli OAuth subprocess (mirrors claude/codex pattern).
    Used when gemini-cli is installed + ~/.gemini/oauth_creds.json exists. Free for Pafi's
    Google account; free-tier API key has limit=0 on gemini-3.1-pro.
    """
    import shutil as _shutil, pathlib as _pathlib
    if not _shutil.which("gemini"):
        raise PermanentProviderError("gemini", "gemini-cli not installed; run `npm i -g @google/gemini-cli`")
    if not (_pathlib.Path.home() / ".gemini" / "oauth_creds.json").exists():
        raise PermanentProviderError("gemini", "no OAuth creds at ~/.gemini/oauth_creds.json; run `gemini` once to log in")

    prompt = f"# System Instructions\n\n{system}\n\n# User Request\n\n{user}\n"
    # NOTE: --yolo causes rc=1 in subprocess mode (some interactive-approval quirk).
    # Default approval-mode is safe for text-only generation (no tool calls).
    # Ensure headless mode works in non-trusted workspaces
    env = os.environ.copy()
    env.setdefault("GEMINI_CLI_TRUST_WORKSPACE", "true")
    cmd = ["gemini", "--skip-trust", "--model", model]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=env,
        )
    except subprocess.TimeoutExpired:
        raise TransientProviderError("gemini", f"gemini-cli timed out after {timeout_s}s")

    if result.returncode != 0:
        err = (result.stderr or "").lower()
        if any(code in err for code in ("capacity", "resource_exhausted", "rate", "429", "500", "502", "503", "504")):
            raise TransientProviderError("gemini", f"gemini-cli transient: {result.stderr[:200]}")
        if "auth" in err or "401" in err or "login" in err:
            raise PermanentProviderError("gemini", f"gemini-cli auth: {result.stderr[:200]}")
        raise PermanentProviderError("gemini", f"gemini-cli error rc={result.returncode}: {result.stderr[:200]}")

    text = (result.stdout or "").strip()
    # gemini-cli emits some startup warnings on stderr ("256-color support", "Ripgrep…") — ignore.
    # No token counts from CLI; estimate from char counts (~4 chars/token).
    tokens_in = len(prompt.encode("utf-8")) // 4
    tokens_out = len(text.encode("utf-8")) // 4
    return {"text": text, "tokens": {"in": tokens_in, "out": tokens_out}}


def _call_google(
    provider: str,
    model_id: str,
    system: str,
    user: str,
    max_tokens: int,
    temperature: float,
    timeout_s: float,
    **provider_kwargs: Any,
) -> dict[str, Any]:
    # v1.0.4: prefer gemini-cli OAuth subprocess (mirrors claude/codex pattern + bypasses
    # paid-tier-only models like gemini-3.1-pro that block free-tier API keys).
    # Falls back to SDK if gemini-cli unavailable.
    import shutil as _shutil, pathlib as _pathlib
    cli_available = (
        _shutil.which("gemini")
        and (_pathlib.Path.home() / ".gemini" / "oauth_creds.json").exists()
    )
    if cli_available:
        return _call_gemini_subprocess(
            model=model_id, system=system, user=user, timeout_s=timeout_s,
        )

    # SDK fallback (legacy path)
    try:
        client = _get_gemini_client()
    except PermanentProviderError:
        raise

    try:
        if _GOOGLE_SDK == "genai":
            gen_config: dict[str, Any] = {
                "system_instruction": system,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
            # Forward thinking_config for Gemini max-reasoning (Task 4-6)
            if "thinking_config" in provider_kwargs:
                gen_config["thinking_config"] = provider_kwargs["thinking_config"]
            for k, v in provider_kwargs.items():
                if k != "thinking_config" and k not in gen_config:
                    gen_config[k] = v
            response = client.models.generate_content(
                model=model_id,
                contents=user,
                config=gen_config,
            )
            text = response.text
            usage = response.usage_metadata
            tokens_in = getattr(usage, "prompt_token_count", 0) or 0
            tokens_out = getattr(usage, "candidates_token_count", 0) or 0
        else:
            # google.generativeai legacy SDK
            model_obj = client.GenerativeModel(
                model_name=model_id,
                system_instruction=system,
            )
            gen_config_obj: dict[str, Any] = {
                "max_output_tokens": max_tokens,
                "temperature": temperature,
            }
            if "thinking_config" in provider_kwargs:
                # FIX-6: legacy google.generativeai SDK does not accept thinking_config
                # in GenerationConfig — strip it with a stderr warning.
                sys.stderr.write(
                    "[google.generativeai legacy SDK] thinking_config ignored — "
                    "install google-genai for thinking support\n"
                )
            for k, v in provider_kwargs.items():
                if k != "thinking_config" and k not in gen_config_obj:
                    gen_config_obj[k] = v
            gc = client.types.GenerationConfig(**gen_config_obj)
            response = model_obj.generate_content(user, generation_config=gc)
            text = response.text
            usage = getattr(response, "usage_metadata", None)
            tokens_in = getattr(usage, "prompt_token_count", 0) or 0
            tokens_out = getattr(usage, "candidates_token_count", 0) or 0

        return {"text": text, "tokens": {"in": tokens_in, "out": tokens_out}}
    except Exception as exc:
        kind, msg = _classify_google_error(exc)
        if kind == "transient":
            raise TransientProviderError(provider, msg) from exc
        raise PermanentProviderError(provider, msg) from exc
