"""Root conftest — ensures `app` package is importable for tests."""

import sys
from pathlib import Path

# Add backend directory to sys.path so tests can import `app.*`
sys.path.insert(0, str(Path(__file__).parent))
