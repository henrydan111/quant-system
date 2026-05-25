"""Compatibility wrapper for quarterly income VIP backfills.

This preserves the historical script entrypoint while routing to the generic
quarterly-statement fetcher.
"""

from __future__ import annotations

import sys

from fetch_quarterly_statements import main as fetch_quarterly_statements_main


def main() -> None:
    sys.argv = [sys.argv[0], "--dataset", "income", *sys.argv[1:]]
    fetch_quarterly_statements_main()


if __name__ == "__main__":
    main()
