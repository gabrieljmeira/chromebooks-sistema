"""SQLite local / Turso, migração aditiva e transações explícitas."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


def connect():
    url = os.getenv("TURSO_DATABASE_URL", "").strip()
    if url:
        if urlsplit(url).scheme not in ("https", "libsql", "turso"):
            raise RuntimeError("Use uma URL Turso com transporte HTTPS.")
        token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Defina TURSO_AUTH_TOKEN.")
        import turso_serverless

        db = turso_serverless.connect(url, auth_token=token, isolation_level=None)
        db.execute("PRAGMA foreign_keys = ON")
        return db
    if os.getenv("VERCEL"):
        raise RuntimeError(
            "Na Vercel é obrigatório configurar o banco Turso persistente."
        )
    path = Path(os.getenv("LOCAL_DB_PATH", "instance/chromebooks.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=15, isolation_level=None)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    return db


def rows(cursor):
    fields = [c[0] for c in cursor.description or []]
    return [dict(zip(fields, row)) for row in cursor.fetchall()]


def one(cursor):
    result = rows(cursor)
    return result[0] if result else None


@contextmanager
def transaction():
    db = connect()
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with transaction() as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS devices (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE)"
        )
        db.execute("""CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, professor_name TEXT NOT NULL,
            room TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
            requested_at TEXT NOT NULL, expected_return_at TEXT NOT NULL,
            confirmed_at TEXT, returned_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','active','returned','cancelled'))
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS loan_devices (
            loan_id INTEGER NOT NULL REFERENCES loans(id), device_id INTEGER NOT NULL REFERENCES devices(id),
            returned_at TEXT, PRIMARY KEY(loan_id,device_id))""")
        fields = {c["name"] for c in rows(db.execute("PRAGMA table_info(loans)"))}
        for name, definition in [
            ("start_at", "TEXT"),
            ("kind", "TEXT NOT NULL DEFAULT 'now'"),
            ("needs_review", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if name not in fields:
                db.execute(f"ALTER TABLE loans ADD COLUMN {name} {definition}")
        if "needs_review" not in fields:
            db.execute(
                "UPDATE loans SET needs_review=1 WHERE status IN ('active','returned')"
            )
        db.execute(
            "UPDATE loans SET start_at=COALESCE(confirmed_at,requested_at) WHERE start_at IS NULL"
        )
        if "returned_at" not in {
            c["name"] for c in rows(db.execute("PRAGMA table_info(loan_devices)"))
        }:
            db.execute("ALTER TABLE loan_devices ADD COLUMN returned_at TEXT")
        # Nunca sobrescreve as atribuições antigas: elas não provam entrega física.
        db.execute(
            """CREATE TABLE IF NOT EXISTS allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL REFERENCES loans(id),
            device_id INTEGER NOT NULL REFERENCES devices(id), delivered_at TEXT NOT NULL, returned_at TEXT)"""
        )
        db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS one_active_device ON allocations(device_id) WHERE returned_at IS NULL"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS allocations_loan ON allocations(loan_id)"
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS loans_status_interval ON loans(status,start_at,expected_return_at)"
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS operations (
            token TEXT PRIMARY KEY, payload TEXT NOT NULL, loan_id INTEGER NOT NULL REFERENCES loans(id))"""
        )
        db.execute("""CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, loan_id INTEGER NOT NULL REFERENCES loans(id),
            action TEXT NOT NULL, happened_at TEXT NOT NULL, detail TEXT NOT NULL)""")
        db.execute("CREATE INDEX IF NOT EXISTS audit_loan ON audit(loan_id,id)")
        db.execute("""CREATE TABLE IF NOT EXISTS rate_limits (
            key TEXT PRIMARY KEY, hits INTEGER NOT NULL, expires INTEGER NOT NULL)""")
        for i in range(1, 21):
            db.execute(
                "INSERT OR IGNORE INTO devices(id,code) VALUES (?,?)", (i, f"CH-{i:03}")
            )
        actual = rows(db.execute("SELECT id,code FROM devices ORDER BY id"))
        if actual != [{"id": i, "code": f"CH-{i:03}"} for i in range(1, 21)]:
            raise RuntimeError(
                "Inventário diferente de CH-001 a CH-020; conferir antes de migrar."
            )
