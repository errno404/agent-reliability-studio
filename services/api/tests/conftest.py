import pytest
from app import config, db, seed
from app.models import Base
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    """One seeded demo database (samples=1 keeps it fast) shared by read-only tests."""
    path = tmp_path_factory.mktemp("db") / "test.db"
    config.get_settings.cache_clear()
    eng = db.reset_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    seed.SAMPLES = 1
    with db.session_scope() as s:
        seed.seed_all(s)
    return f"sqlite:///{path}"


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


@pytest.fixture
def fresh_db(tmp_path):
    eng = db.reset_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
    Base.metadata.create_all(eng)
    yield eng
