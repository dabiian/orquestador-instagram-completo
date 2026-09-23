"""Executable test harness for the self_healer package."""

from __future__ import annotations

import sys
from pathlib import Path


DEFAULT_TEST_PATH = str(Path(__file__).resolve().parent / "tests")


def main(argv: list[str] | None = None) -> int:
    try:
        import pytest
    except ImportError:
        print("pytest is not installed. Install it with: python -m pip install self_healer[test]")
        return 1

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = [DEFAULT_TEST_PATH]
    return pytest.main(args)


if __name__ == "__main__":
    raise SystemExit(main())
