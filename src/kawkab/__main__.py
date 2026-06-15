"""Entry point for Kawkab AI.

Usage:
    python -m kawkab
    kawkab (after pip install)
"""

import sys
from pathlib import Path


def main() -> int:
    """Launch the Kawkab AI desktop application."""
    try:
        from kawkab.app import run_app
    except ImportError as e:
        print(f"Error: Missing dependency - {e}", file=sys.stderr)
        print("Install dependencies with: uv sync", file=sys.stderr)
        return 1

    return run_app()


if __name__ == "__main__":
    sys.exit(main())
