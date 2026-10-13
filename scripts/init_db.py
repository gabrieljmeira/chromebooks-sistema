"""Inicializa/migra sem apagar dados. Faz backup automático do SQLite existente."""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv()
from database import init_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Autoriza inicialização/migração do Turso configurado; faça backup no provedor antes.",
    )
    args = parser.parse_args()
    remote = bool(os.getenv("TURSO_DATABASE_URL", "").strip())
    if remote and not args.remote:
        parser.error(
            "Banco remoto configurado. Faça backup no Turso e use --remote explicitamente."
        )
    if args.remote and not remote:
        parser.error(
            "--remote exige TURSO_DATABASE_URL; não inicializa SQLite por engano."
        )
    path = Path(os.getenv("LOCAL_DB_PATH", "instance/chromebooks.db"))
    if not remote and path.exists():
        backup = path.with_name(
            path.name
            + ".backup-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            + ".sqlite"
        )
        source = sqlite3.connect(path)
        destination = sqlite3.connect(backup)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        backup.chmod(0o600)
        print("Backup local criado:", backup)
    init_db()
    print(
        "Banco preparado com CH-001 a CH-020. Confira os registros antigos sinalizados no histórico da TI."
    )


if __name__ == "__main__":
    main()
