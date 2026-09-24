import pytest
from fastapi.testclient import TestClient

from app.infrastructure import database
from app.main import app


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", path)
    monkeypatch.setenv("BASE_URL", "http://test.local")
    return path


@pytest.fixture
def client(db_path):
    return TestClient(app)


@pytest.fixture
def conn(tmp_path):
    connection = database.connect(str(tmp_path / "unit.db"))
    yield connection
    connection.close()


@pytest.fixture(autouse=True)
def _reset_dependency_overrides():
    yield
    app.dependency_overrides.clear()
