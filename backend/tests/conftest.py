import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ASKDATA_STATE_DB_PATH", str(Path(tempfile.mkdtemp()) / "state.sqlite3"))

import pytest  # noqa: E402

from app.schema_index import get_index  # noqa: E402


@pytest.fixture(scope="session")
def index():
    """Requires the seeded demo database (see data/seed.py / docker-compose)."""
    return get_index(refresh=True)
