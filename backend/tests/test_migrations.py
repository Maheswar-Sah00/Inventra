"""Fresh database -> run Alembic migrations -> users table exists -> authentication works."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.auth.rate_limit import reset_rate_limits
from app.core.database import get_db
from app.main import create_app
from tests.conftest import auth_headers, login, signup

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_migrations_build_a_working_schema_from_scratch(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    monkeypatch.chdir(BACKEND_DIR)
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "DATABASE_URL", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")

    engine = create_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert {"users", "password_reset_otps", "alembic_version"} <= tables
    assert {c["name"] for c in inspect(engine).get_columns("users")} >= {
        "id", "name", "email", "password_hash", "role", "is_active", "created_at", "updated_at",
    }

    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    reset_rate_limits()
    with TestClient(app) as client:
        assert signup(client).status_code == 201
        token = login(client).json()["access_token"]
        assert client.get("/api/users/me", headers=auth_headers(token)).status_code == 200

    command.downgrade(config, "base")
    assert "users" not in inspect(engine).get_table_names()
    engine.dispose()
