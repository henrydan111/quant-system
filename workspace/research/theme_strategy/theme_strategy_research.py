from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from src.alpha_research.theme_strategy.cli import main


if __name__ == "__main__":
    main()
