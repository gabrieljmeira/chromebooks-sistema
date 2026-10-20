"""Backup lógico consistente e restauração validada em um novo SQLite."""

import json
import os
import sqlite3
import tempfile
from pathlib import Path

from database import connect, init_db, rows
import services as s

TABLES = ("devices", "loans", "loan_devices", "allocations", "operations", "audit", "rate_limits", "unavailable_devices", "management_audit", "feature_operations", "admin_users")
FORMAT = "chromebooks-backup-v1"


def snapshot():
    db = connect()
    try:
        db.execute("BEGIN")
        data = {"format": FORMAT, "created_at": s.stamp(), "tables": {table: rows(db.execute(f"SELECT * FROM {table}")) for table in TABLES}}
        db.commit()
        return data
    finally:
        db.close()


def write_private(path):
    path = Path(path)
    content = json.dumps(snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def restore(source, destination):
    """Nunca sobrescreve banco existente nem modifica produção."""
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise ValueError("O destino já existe. Escolha um arquivo novo para testar a restauração.")
    if source.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Backup acima de 100 MB; faça uma restauração assistida.")
    content = json.loads(source.read_text(encoding="utf-8"))
    if content.get("format") != FORMAT or set(content.get("tables", {})) != set(TABLES):
        raise ValueError("Formato de backup inválido ou incompleto.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="restore-", suffix=".sqlite", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    previous = {key: os.environ.get(key) for key in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN", "VERCEL", "LOCAL_DB_PATH")}
    try:
        for key in previous:
            os.environ.pop(key, None)
        os.environ["LOCAL_DB_PATH"] = str(temporary)
        init_db()
        db = sqlite3.connect(temporary)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            db.execute("PRAGMA defer_foreign_keys=ON")
            for table in reversed(TABLES):
                db.execute(f"DELETE FROM {table}")
            for table in TABLES:
                allowed = {item[1] for item in db.execute(f"PRAGMA table_info({table})")}
                for row in content["tables"][table]:
                    if not isinstance(row, dict) or set(row) != allowed:
                        raise ValueError(f"Colunas inválidas no backup: {table}.")
                    columns = sorted(allowed)
                    db.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", [row[key] for key in columns])
            if db.execute("PRAGMA foreign_key_check").fetchall() or db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("O backup não passou na verificação de integridade.")
            actual = db.execute("SELECT id,code FROM devices ORDER BY id").fetchall()
            if actual != [(i, f"CH-{i:03}") for i in range(1, 21)]:
                raise ValueError("Inventário inesperado no backup.")
            db.commit()
        finally:
            db.close()
        # Publicação exclusiva, inclusive se outro processo criar o destino.
        os.link(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
