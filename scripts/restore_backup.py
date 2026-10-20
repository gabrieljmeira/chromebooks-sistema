"""Restaura somente em arquivo local novo; não sobrescreve produção."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backups import restore

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    try:
        restore(args.source, args.destination)
    except Exception as exc:
        print("Falha na restauração:", type(exc).__name__, "Use um backup válido e um destino novo.", file=sys.stderr)
        sys.exit(1)
    print("Restauração e integridade verificadas:", args.destination)
