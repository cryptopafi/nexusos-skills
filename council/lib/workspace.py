"""
workspace.py -- Council workspace directory management.

Creates per-task workspace directories under ~/.nexus/workspace/council/<task-id>/.
Stdlib only -- no external dependencies. Uses pathlib throughout.

task_id is not a secret; collision avoidance only. Do not trust task_id as an ACL token.
"""

import random
import string
import os
from datetime import datetime, timezone
from pathlib import Path


_TASK_ID_SUFFIX_CHARS: str = string.ascii_lowercase + string.digits
_TASK_ID_SUFFIX_LENGTH: int = 4

# Subdirectories created under each task workspace.
_WORKSPACE_SUBDIRS: tuple[str, ...] = (
    "advisors",
    "anonymized",
    "verdict",
)


def create(task_id: str | None = None, max_attempts: int = 3) -> Path:
    """
    Creates ~/.nexus/workspace/council/<task_id>/ with standard subdirectories.

    If task_id is None, generate one and retry on collision (max_attempts).
    If task_id is provided, do single attempt as before (caller picked the id).

    Returns the Path to the task workspace root.

    Raises:
        FileExistsError: if the task_id directory already exists and task_id
                         was provided explicitly, or if all auto-generated
                         attempts collide ("task_id space exhausted within minute").
    """
    if task_id is not None:
        # Explicit id: single attempt, original behaviour preserved.
        base = _council_base()
        task_dir = base / task_id
        if task_dir.exists():
            raise FileExistsError(
                f"Council workspace already exists for task_id={task_id!r}: {task_dir}. "
                "Generate a new task_id and retry."
            )
        task_dir.mkdir(parents=True, exist_ok=False)
        for subdir in _WORKSPACE_SUBDIRS:
            (task_dir / subdir).mkdir(parents=False, exist_ok=False)
        return task_dir

    # Auto-generate with retry loop.
    base = _council_base()
    last_error: FileExistsError | None = None
    for _ in range(max_attempts):
        candidate = generate_task_id()
        task_dir = base / candidate
        if task_dir.exists():
            last_error = FileExistsError(
                f"Council workspace already exists for task_id={candidate!r}: {task_dir}. "
                "Generate a new task_id and retry."
            )
            continue
        task_dir.mkdir(parents=True, exist_ok=False)
        for subdir in _WORKSPACE_SUBDIRS:
            (task_dir / subdir).mkdir(parents=False, exist_ok=False)
        return task_dir

    raise FileExistsError(
        f"task_id space exhausted within minute after {max_attempts} attempts."
    ) from last_error


def generate_task_id() -> str:
    """
    Returns a unique council task identifier.

    Format: council-YYYYMMDD-HHMM-<4 random lowercase alphanumeric chars>
    Example: council-20260519-1453-a7b2
    """
    now = datetime.now(tz=timezone.utc)
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M")
    suffix = "".join(
        random.choices(_TASK_ID_SUFFIX_CHARS, k=_TASK_ID_SUFFIX_LENGTH)
    )
    return f"council-{date_part}-{time_part}-{suffix}"


def _council_base() -> Path:
    """Returns the council workspace base directory as a Path object."""
    workspace_dir = os.environ.get("COUNCIL_WORKSPACE_DIR")
    if workspace_dir:
        return Path(workspace_dir).expanduser()
    return Path.home() / ".nexus" / "workspace" / "council"
