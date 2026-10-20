"""Executar por tarefa agendada; lê credenciais do .env, nunca as imprime."""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
from backups import write_private

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="backups")
    args = parser.parse_args()
    directory = Path(args.directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / ("chromebooks-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json")
    try:
        write_private(target)
    except Exception as exc:
        print("Falha no backup:", type(exc).__name__, "Confira a conexão e o diagnóstico do projeto.", file=sys.stderr)
        sys.exit(1)
    print("Backup concluído:", target)
