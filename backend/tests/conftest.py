import sys
from pathlib import Path

# Add backend/ to sys.path so `from pipeline.xxx import` works in tests
sys.path.insert(0, str(Path(__file__).parent.parent))
