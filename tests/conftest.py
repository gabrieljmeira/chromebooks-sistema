import pytest

from database import init_db


@pytest.fixture(autouse=True)
def local_db(monkeypatch, tmp_path):
    # Os testes nunca devem usar credenciais ou bancos do .env do desenvolvedor.
    monkeypatch.setenv('PYTHON_DOTENV_DISABLED', '1')
    monkeypatch.delenv('TURSO_DATABASE_URL', raising=False)
    monkeypatch.delenv('TURSO_AUTH_TOKEN', raising=False)
    monkeypatch.setenv('LOCAL_DB_PATH', str(tmp_path / 'test.db'))
    init_db()
