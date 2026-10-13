"""Operator-only preparation; no project or model execution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from credproof_safety.runtime_setup import main

if __name__ == '__main__':
    raise SystemExit(main())
