"""SQLite local / Turso, migração aditiva e transações explícitas."""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit


class DatabaseUnavailable(RuntimeError):
    """Falha de conexão/configuração com mensagem pública sem credenciais."""


FEATURE_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS unavailable_devices (device_id INTEGER PRIMARY KEY REFERENCES devices(id), reason TEXT NOT NULL, changed_at TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS management_audit (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, happened_at TEXT NOT NULL, actor TEXT NOT NULL, detail TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS feature_operations (token TEXT PRIMARY KEY, payload TEXT NOT NULL, result TEXT NOT NULL)",
    "CREATE TABLE IF NOT EXISTS admin_users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('manager','technician')), active INTEGER NOT NULL CHECK(active IN (0,1)), version TEXT NOT NULL)",
)
_prepared = set()


class Connection:
    """Uniformiza erros dos drivers; não repete operações de escrita."""

    def __init__(self, db, errors):
        self.db, self.errors = db, errors

    def execute(self, *args):
        try:
            return self.db.execute(*args)
        except self.errors as exc:
            raise DatabaseUnavailable("Banco indisponível. A TI deve conferir a conexão e a inicialização do banco.") from exc

    def commit(self):
        try:
            return self.db.commit()
        except self.errors as exc:
            raise DatabaseUnavailable("Não foi possível confirmar a gravação no banco. Confira o painel antes de repetir.") from exc

    def rollback(self):
        return self.db.rollback()

    def __getattr__(self, name):
        return getattr(self.db, name)


def connect():
    url = os.getenv("TURSO_DATABASE_URL", "").strip()
    if url:
        try:
            valid_url = urlsplit(url).scheme in ("https", "libsql", "turso") and bool(urlsplit(url).hostname)
        except ValueError:
            valid_url = False
        if not valid_url:
            raise DatabaseUnavailable("Configuração do banco inválida. A TI deve conferir TURSO_DATABASE_URL.")
        token = os.getenv("TURSO_AUTH_TOKEN", "").strip()
        if not token:
            raise DatabaseUnavailable("Banco não configurado: a TI deve definir TURSO_AUTH_TOKEN na hospedagem.")
        try:
            import turso_serverless
        except ImportError as exc:
            raise DatabaseUnavailable("Driver do banco ausente. A TI deve conferir as dependências do deploy.") from exc

        try:
            db = Connection(turso_serverless.connect(url, auth_token=token, isolation_level=None), (turso_serverless.OperationalError, OSError))
        except (turso_serverless.Error, OSError) as exc:
            raise DatabaseUnavailable("Banco indisponível. A TI deve conferir URL e token na hospedagem.") from exc
        identity = ("turso", url)
    else:
        if os.getenv("VERCEL"):
            raise DatabaseUnavailable("Banco Turso não configurado: a TI deve definir TURSO_DATABASE_URL na hospedagem.")
        path = Path(os.getenv("LOCAL_DB_PATH", "instance/chromebooks.db"))
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            db = Connection(sqlite3.connect(path, timeout=15, isolation_level=None), (sqlite3.OperationalError,))
        except sqlite3.Error as exc:
            raise DatabaseUnavailable("Banco local indisponível. Confira LOCAL_DB_PATH e as permissões da pasta.") from exc
        db.execute("PRAGMA busy_timeout = 15000")
        identity = ("local", str(path.resolve()))
    try:
        db.execute("PRAGMA foreign_keys = ON")
        if identity not in _prepared:
            # Migração apenas aditiva: uma transação, segura entre instâncias.
            # Não altera empréstimos, códigos, senhas ou horários existentes.
            db.execute("BEGIN IMMEDIATE")
            try:
                for sql in FEATURE_SCHEMA:
                    db.execute(sql)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
                raise
            _prepared.add(identity)
        return db
    except Exception:
        db.close()
        raise


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
        try:
            db.rollback()
        except Exception:
            pass  # Preserva a falha original; nenhuma escrita é repetida automaticamente.
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
