"""Diagnóstico sem imprimir URL, token, chave ou hash."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from database import DatabaseUnavailable, connect

if __name__ == "__main__":
    for key in ("SECRET_KEY", "ADMIN_PASSWORD_HASH", "TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
        print(key + ": " + ("definida" if os.getenv(key, "").strip() else "ausente"))
    try:
        db = connect()
        try:
            db.execute("SELECT start_at,needs_review FROM loans LIMIT 1")
            db.execute("SELECT id FROM allocations LIMIT 1")
            print("Banco: conexão e esquema básico OK")
        finally:
            db.close()
    except DatabaseUnavailable as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
