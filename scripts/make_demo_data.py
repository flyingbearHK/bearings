"""Write the demo export files only (same as `uv run bearings demo --files-only`).

Prefer `uv run bearings demo`, which also loads, profiles and relates the data into data/demo.duckdb.
"""
import sys
from pathlib import Path

from bearings.demo import generate

if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("demo")
    print(generate(out))
