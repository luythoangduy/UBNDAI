"""Reset and seed the deterministic local hackathon showcase."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import settings  # noqa: E402
from src.services.officer_store import store  # noqa: E402


if __name__ == "__main__":
    store.reset_demo_data()
    mode = "persistent database" if settings.persistence_enabled else "in-memory startup seed"
    print(f"Demo data ready ({mode}): case-demo-001, document-demo-001")
