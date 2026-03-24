import os
import shutil
import tempfile
from pathlib import Path

import pytest


TEST_ARTIFACTS_DIR = Path(tempfile.mkdtemp(prefix="smartpantry-tests-"))
TEST_DB_PATH = TEST_ARTIFACTS_DIR / "smartpantry-test.db"
TEST_STORAGE_DIR = TEST_ARTIFACTS_DIR / "storage"

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
os.environ["LOCAL_STORAGE_DIR"] = str(TEST_STORAGE_DIR)

from app.core.config import get_settings

get_settings.cache_clear()

from app.db import configure_database, engine
from app.main import app

configure_database(os.environ["DATABASE_URL"])


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_artifacts():
    yield
    engine.dispose()
    shutil.rmtree(TEST_ARTIFACTS_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    app.state.rate_limiter.clear()
    yield
    app.state.rate_limiter.clear()
