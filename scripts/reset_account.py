"""Recuperação por quem já controla as credenciais do banco, sem rota pública."""
import argparse
from getpass import getpass
from pathlib import Path
import secrets
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
import accounts
import services

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    args = parser.parse_args()
    user = next((item for item in accounts.list_users() if item["username"] == args.username.lower()), None)
    if not user:
        raise SystemExit("Conta não encontrada. Nenhuma alteração realizada.")
    password = getpass("Nova senha (mínimo 12 caracteres): ")
    if password != getpass("Confirme a nova senha: "):
        raise SystemExit("As senhas não conferem. Nenhuma alteração realizada.")
    services.actor.set("Recuperação local da TI")
    accounts.update_user(user["id"], "manager", True, password, secrets.token_urlsafe(32))
    print("Conta recuperada como gestor. Sessões anteriores encerradas e recuperação auditada.")
