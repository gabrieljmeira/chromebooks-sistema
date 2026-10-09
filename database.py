"""Adaptador simples: SQLite local ou Turso remoto (engine Turso)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def connect():
    url = os.getenv("TURSO_DATABASE_URL", "").strip()
    if url:
        token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Defina TURSO_AUTH_TOKEN para acessar o banco remoto.")
        # A conexão HTTP funciona sem arquivo local, inclusive na Vercel.
        import turso_serverless
        return turso_serverless.connect(url, auth_token=token)

    path = Path(os.getenv("LOCAL_DB_PATH", "instance/chromebooks.db"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def rows(cursor):
    fields = [column[0] for column in cursor.description or []]
    return [dict(zip(fields, row)) for row in cursor.fetchall()]


def one(cursor):
    results = rows(cursor)
    return results[0] if results else None


def init_db():
    db = connect()
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY,
                code TEXT NOT NULL UNIQUE
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                professor_name TEXT NOT NULL,
                room TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity BETWEEN 1 AND 20),
                requested_at TEXT NOT NULL,
                expected_return_at TEXT NOT NULL,
                confirmed_at TEXT,
                returned_at TEXT,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','active','returned','cancelled'))
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS loan_devices (
                loan_id INTEGER NOT NULL,
                device_id INTEGER NOT NULL,
                PRIMARY KEY (loan_id, device_id),
                FOREIGN KEY (loan_id) REFERENCES loans(id),
                FOREIGN KEY (device_id) REFERENCES devices(id)
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS ix_loans_status ON loans(status)")
        for i in range(1, 21):
            db.execute("INSERT OR IGNORE INTO devices (id, code) VALUES (?, ?)", (i, f"CH-{i:03}"))
        db.commit()
    finally:
        db.close()


AVAILABLE_SQL = """
    SELECT d.id, d.code FROM devices d
    WHERE NOT EXISTS (
        SELECT 1 FROM loan_devices ld
        JOIN loans l ON l.id = ld.loan_id
        WHERE ld.device_id = d.id AND l.status = 'active'
    )
    ORDER BY d.id
"""
