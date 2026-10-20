"""Contas locais da TI; a primeira conta encerra o acesso compartilhado."""

import re
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

import management as m
import services as s
from database import connect, one, rows, transaction


def configured():
    db = connect()
    try:
        return one(db.execute("SELECT id FROM admin_users LIMIT 1")) is not None
    finally:
        db.close()


def get_user(user_id):
    db = connect()
    try:
        return one(db.execute("SELECT * FROM admin_users WHERE id=?", (user_id,)))
    finally:
        db.close()


def authenticate(username, password):
    db = connect()
    try:
        user = one(db.execute("SELECT * FROM admin_users WHERE username=?", (str(username).strip().lower(),)))
        # Mesmo custo aproximado quando o usuário não existe; nenhum hash sai da camada.
        stored = user["password_hash"] if user else generate_password_hash("usuario-inexistente")
        valid = check_password_hash(stored, password)
        return user if user and user["active"] and valid else None
    finally:
        db.close()


def list_users():
    db = connect()
    try:
        return rows(db.execute("SELECT id,username,role,active FROM admin_users ORDER BY username"))
    finally:
        db.close()


def password_value(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 1024:
        raise s.ValidationError("Use uma senha de 12 a 1024 caracteres.")
    return value


def create_user(username, password, role, token, bootstrap=False):
    username = str(username or "").strip().lower()
    password = password_value(password)
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", username):
        raise s.ValidationError("Use um usuário de 3 a 64 caracteres: letras sem acentos, números, ponto, hífen ou sublinhado.")
    if role not in ("manager", "technician"):
        raise s.ValidationError("Selecione um perfil válido.")
    fingerprint = s.payload("create_user", username, password, role)
    with transaction() as db:
        if m.feature_repeat(db, token, fingerprint):
            return
        exists = one(db.execute("SELECT id FROM admin_users LIMIT 1"))
        if bootstrap and exists:
            raise s.ValidationError("A primeira conta já foi criada. Entre com seu usuário individual.")
        if not exists and role != "manager":
            raise s.ValidationError("A primeira conta precisa ser Gestor da TI.")
        if one(db.execute("SELECT id FROM admin_users WHERE username=?", (username,))):
            raise s.ValidationError("Este usuário já está cadastrado.")
        db.execute("INSERT INTO admin_users(username,password_hash,role,active,version) VALUES (?,?,?,1,?)", (username, generate_password_hash(password), role, secrets.token_urlsafe(32)))
        m.audit(db, "conta_criada", {"username": username, "role": role}, token, fingerprint)


def update_user(user_id, role, active, password, token):
    if role not in ("manager", "technician"):
        raise s.ValidationError("Selecione um perfil válido.")
    if password:
        password_value(password)
    fingerprint = s.payload("update_user", user_id, role, active, password)
    with transaction() as db:
        if m.feature_repeat(db, token, fingerprint):
            return
        user = one(db.execute("SELECT * FROM admin_users WHERE id=?", (user_id,)))
        if not user:
            raise s.ValidationError("Conta não encontrada.")
        count = one(db.execute("SELECT COUNT(*) AS n FROM admin_users WHERE role='manager' AND active=1"))["n"]
        if user["active"] and user["role"] == "manager" and (not active or role != "manager") and count <= 1:
            raise s.ValidationError("Mantenha pelo menos um gestor ativo para não perder o acesso.")
        db.execute("UPDATE admin_users SET role=?,active=?,password_hash=?,version=? WHERE id=?", (role, int(active), generate_password_hash(password) if password else user["password_hash"], secrets.token_urlsafe(32), user_id))
        m.audit(db, "conta_alterada", {"username": user["username"], "before": {"role": user["role"], "active": user["active"]}, "after": {"role": role, "active": int(active)}, "password_reset": bool(password)}, token, fingerprint)


def change_password(user_id, old, new, token):
    new = password_value(new)
    fingerprint = s.payload("change_password", user_id, new)
    with transaction() as db:
        if m.feature_repeat(db, token, fingerprint):
            return
        user = one(db.execute("SELECT * FROM admin_users WHERE id=? AND active=1", (user_id,)))
        if not user or not check_password_hash(user["password_hash"], str(old or "")):
            raise s.ValidationError("A senha atual não confere.")
        db.execute("UPDATE admin_users SET password_hash=?,version=? WHERE id=?", (generate_password_hash(new), secrets.token_urlsafe(32), user_id))
        m.audit(db, "senha_alterada", {"username": user["username"]}, token, fingerprint)
