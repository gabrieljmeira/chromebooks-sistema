"""Servidor exclusivo do teste visual, com banco temporário e relógio fixo."""
import os
import secrets
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
for key in ('TURSO_DATABASE_URL', 'TURSO_AUTH_TOKEN', 'VERCEL', 'COOKIE_SECURE'):
    os.environ.pop(key, None)
os.environ['PYTHON_DOTENV_DISABLED'] = '1'
os.environ['SECRET_KEY'] = secrets.token_urlsafe(48)
from werkzeug.security import generate_password_hash
os.environ['ADMIN_PASSWORD_HASH'] = generate_password_hash('senha-teste-browser')
import services
services.now = lambda: datetime(2026, 10, 19, 10, 0, tzinfo=services.TZ)
from database import init_db
with tempfile.TemporaryDirectory(prefix='chromebooks-ui-') as directory:
    os.environ['LOCAL_DB_PATH'] = str(Path(directory) / 'test.db')
    init_db()
    from app import app
    app.run(port=8765, debug=False, use_reloader=False)
