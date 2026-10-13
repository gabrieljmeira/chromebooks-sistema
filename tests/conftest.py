import importlib
import secrets
from datetime import datetime
import pytest
import services
from database import init_db


@pytest.fixture(autouse=True)
def local_db(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    for name in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "VERCEL", "COOKIE_SECURE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LOCAL_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(
        services, "now", lambda: datetime(2026, 10, 13, 10, 0, tzinfo=services.TZ)
    )
    init_db()


@pytest.fixture
def client(monkeypatch):
    from werkzeug.security import generate_password_hash

    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(48))
    monkeypatch.setenv(
        "ADMIN_PASSWORD_HASH", generate_password_hash("senha-exclusiva-teste")
    )
    import app

    importlib.reload(app)
    app.app.config["TESTING"] = True
    return app.app.test_client()
