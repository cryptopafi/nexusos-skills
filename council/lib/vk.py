"""
vk.py -- VK (Verification Key) emitter for the /council skill pipeline.

Each pipeline step emits a one-line VK marker to stdout for log-grep enforcement.
Format (canonical per plan §12.5):
  VK:STEP=<step> STATE=<entered|completed|failed> TS=<iso8601Z> TASK=<task_id> [k=v ...]

Stdlib only -- no external dependencies.
"""

import sys
from datetime import datetime, timezone
from typing import Any


_VALID_STATES: frozenset[str] = frozenset({"entered", "completed", "failed"})

# FIX-H1: "orchestrator" removed from _VALID_STEPS (Option A — revert).
# Orchestrator-level lifecycle events no longer emit VK markers directly.
# Each individual pipeline step (triage, normalize, dispatch_*, reconcile, etc.)
# already emits its own entered/completed/failed markers, providing full pipeline
# observability without polluting the pipeline-step enum with a meta-level name.
# All vk.emit("orchestrator", ...) calls in orchestrator.py are removed accordingly.
_VALID_STEPS: frozenset[str] = frozenset({
    "triage",
    "normalize",
    "dispatch_A",
    "dispatch_B",
    "dispatch_C",
    "anonymize",
    "reconcile",
    "debate",
    "ledger",
})


def emit(step: str, state: str, task_id: str, **extra: Any) -> None:
    """
    Emits one VK marker line to stdout.

    Format:
      VK:STEP=<step> STATE=<state> TS=<iso8601Z> TASK=<task_id> [k=v ...]

    Args:
        step:    Pipeline step name. Must be one of the allowed steps.
        state:   Must be one of: entered, completed, failed.
        task_id: Council task identifier (e.g. council-20260519-1453-a7b2).
        **extra: Optional key=value pairs appended to the line (e.g. score=72).

    Raises:
        ValueError: if state or step is not in the allowed set.
    """
    if state not in _VALID_STATES:
        raise ValueError(
            f"Invalid VK state {state!r}. Allowed: {', '.join(sorted(_VALID_STATES))}"
        )
    if step not in _VALID_STEPS:
        raise ValueError(
            f"Invalid VK step {step!r}. "
            f"Allowed: {', '.join(sorted(_VALID_STEPS))}"
        )

    for key, value in extra.items():
        if " " in str(value):
            raise ValueError(
                f"VK extra kwarg {key!r} value {value!r} contains a space, "
                "which breaks line grammar. Use underscore or omit spaces."
            )

    ts = _iso8601_utc_now()
    parts = [
        f"VK:STEP={step}",
        f"STATE={state}",
        f"TS={ts}",
        f"TASK={task_id}",
    ]
    for key, value in extra.items():
        parts.append(f"{key}={value}")

    line = " ".join(parts)
    print(line, flush=True)


def _iso8601_utc_now() -> str:
    """Returns current UTC time as ISO 8601 string ending in Z."""
    now = datetime.now(tz=timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")
