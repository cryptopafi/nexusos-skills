"""
args.py -- CLI argument parser for the /council skill.

Parses /council invocation arguments. Accepts POSIX-style (--depth standard)
and equals-style (--depth=standard) syntax. Returns a plain dict.
Stdlib only -- no click, typer, or argparse extras.
"""

import argparse
from typing import Any


_VALID_DEPTHS = {"quick", "standard", "deep"}
_DEFAULT_DEPTH = "standard"
_DEFAULT_MIN_QUORUM = 3


def parse_args(argv: list[str]) -> dict[str, Any]:
    """
    Parses /council CLI arguments.

    Returns:
        {
          "target": str (required, path or keyword),
          "depth": "quick" | "standard" | "deep"  (default: standard),
          "no_debate": bool (default False),
          "force": bool (default False),
          "min_quorum": 2 | 3 (default 3),
          "keep_chains": bool (default False),
          "force_test": bool (default False),
        }

    Raises ValueError with a clear message on bad arguments.
    """
    parser = _build_parser()

    try:
        namespace = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse calls sys.exit on error; convert to ValueError instead
        raise ValueError(
            f"Argument parse error (exit code {exc.code}). "
            "Usage: /council <target> [--depth quick|standard|deep] "
            "[--no-debate] [--force] [--min-quorum 2|3] "
            "[--keep-chains] [--force-test]"
        ) from exc

    if namespace.target is None:
        raise ValueError(
            "target required. Usage: /council <target> [options]"
        )

    depth = namespace.depth
    if depth not in _VALID_DEPTHS:
        raise ValueError(
            f"Invalid --depth value {depth!r}. "
            f"Allowed: {', '.join(sorted(_VALID_DEPTHS))}"
        )

    min_quorum = namespace.min_quorum
    if min_quorum not in (2, 3):
        raise ValueError(
            f"Invalid --min-quorum value {min_quorum!r}. Allowed: 2, 3"
        )

    return {
        "target": namespace.target,
        "depth": depth,
        "no_debate": namespace.no_debate,
        "force": namespace.force,
        "min_quorum": min_quorum,
        "keep_chains": namespace.keep_chains,
        "force_test": namespace.force_test,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="/council",
        description="Advisor Council skill — 3-model deliberation for ideas and proposals.",
        add_help=True,
    )

    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Path to file or keyword/brief text (required).",
    )
    parser.add_argument(
        "--depth",
        default=_DEFAULT_DEPTH,
        choices=list(_VALID_DEPTHS),
        metavar="quick|standard|deep",
        help=f"Reasoning depth and cost tier (default: {_DEFAULT_DEPTH}).",
    )
    parser.add_argument(
        "--no-debate",
        dest="no_debate",
        action="store_true",
        default=False,
        help="Skip the optional debate round.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Skip triage gate.",
    )
    parser.add_argument(
        "--min-quorum",
        dest="min_quorum",
        type=int,
        default=_DEFAULT_MIN_QUORUM,
        metavar="2|3",
        help="Minimum advisor count for a valid verdict (default: 3).",
    )
    parser.add_argument(
        "--keep-chains",
        dest="keep_chains",
        action="store_true",
        default=False,
        help="Persist reasoning_chain fields locally (chmod 600, auto-purged after 7 days).",
    )
    parser.add_argument(
        "--force-test",
        dest="force_test",
        action="store_true",
        default=False,
        help="Run AC-7 6-permutation order-bias harness.",
    )

    return parser
