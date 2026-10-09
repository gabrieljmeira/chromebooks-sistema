"""Regras de negócio, sem dependência de Flask."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from database import AVAILABLE_SQL, connect, one, rows

TZ = ZoneInfo("America/Sao_Paulo")


class ValidationError(ValueError):
    pass


def now():
    return datetime.now(TZ)


def datetime_label(value):
    if not value:
        return "—"
    return datetime.fromisoformat(value).astimezone(TZ).strftime("%d/%m/%Y %H:%M")


def stock_count():
    db = connect()
    try:
        return len(rows(db.execute(AVAILABLE_SQL)))
    finally:
        db.close()


def _parse_expected(raw):
    try:
        expected = datetime.strptime(raw, "%Y-%m-%dT%H:%M").replace(tzinfo=TZ)
    except (ValueError, TypeError):
        raise ValidationError("Informe uma data e um horário válidos para a devolução.")
    if expected <= now():
        raise ValidationError("A devolução prevista precisa ser no futuro.")
    if expected > now() + timedelta(days=30):
        raise ValidationError("A devolução deve ser prevista para os próximos 30 dias.")
    return expected


def request_loan(professor_name, room, quantity, expected_raw):
    name = str(professor_name or "").strip()
    room = str(room or "").strip()
    if not 3 <= len(name) <= 100:
        raise ValidationError("Informe o nome do professor (3 a 100 caracteres).")
    if not 1 <= len(room) <= 40:
        raise ValidationError("Informe a sala de utilização (até 40 caracteres).")
    try:
        qty = int(quantity)
    except (ValueError, TypeError):
        raise ValidationError("Escolha uma quantidade válida de Chromebooks.")
    if str(quantity) != str(qty) or not 1 <= qty <= 20:
        raise ValidationError("A quantidade precisa ser de 1 a 20.")
    expected = _parse_expected(expected_raw)
    db = connect()
    try:
        # Solicitações não reservam equipamentos; só a TI confirma a entrega.
        if qty > len(rows(db.execute(AVAILABLE_SQL))):
            raise ValidationError("Não há essa quantidade disponível no momento.")
        db.execute("""
            INSERT INTO loans (professor_name, room, quantity, requested_at, expected_return_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, room, qty, now().isoformat(timespec="seconds"), expected.isoformat(timespec="seconds")))
        # SELECT na mesma conexão para recuperar a chave mesmo no driver remoto.
        new_id = one(db.execute("SELECT last_insert_rowid() AS id"))["id"]
        db.commit()
        return int(new_id)
    finally:
        db.close()


def _transaction(db):
    # Serializa confirmação de empréstimos concorrentes no SQLite;
    # Codex deve validar comportamento transacional no Turso remoto.
    db.execute("BEGIN IMMEDIATE")


def confirm_loan(loan_id):
    db = connect()
    try:
        _transaction(db)
        loan = one(db.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)))
        if not loan or loan["status"] != "pending":
            raise ValidationError("Solicitação inexistente ou já processada.")
        if datetime.fromisoformat(loan["expected_return_at"]) <= now():
            raise ValidationError("A previsão de devolução já passou. Cancele e solicite novamente.")
        free = rows(db.execute(AVAILABLE_SQL))
        if len(free) < loan["quantity"]:
            raise ValidationError("Não há Chromebooks suficientes para confirmar esta retirada.")
        for device in free[:loan["quantity"]]:
            db.execute("INSERT INTO loan_devices (loan_id, device_id) VALUES (?, ?)", (loan_id, device["id"]))
        db.execute("""
            UPDATE loans SET status = 'active', confirmed_at = ?
            WHERE id = ? AND status = 'pending'
        """, (now().isoformat(timespec="seconds"), loan_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def return_loan(loan_id):
    db = connect()
    try:
        _transaction(db)
        loan = one(db.execute("SELECT status FROM loans WHERE id = ?", (loan_id,)))
        if not loan or loan["status"] != "active":
            raise ValidationError("Somente retiradas ativas podem ser devolvidas.")
        db.execute("""
            UPDATE loans SET status = 'returned', returned_at = ?
            WHERE id = ? AND status = 'active'
        """, (now().isoformat(timespec="seconds"), loan_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def cancel_loan(loan_id):
    db = connect()
    try:
        _transaction(db)
        loan = one(db.execute("SELECT status FROM loans WHERE id = ?", (loan_id,)))
        if not loan or loan["status"] != "pending":
            raise ValidationError("Somente solicitações pendentes podem ser canceladas.")
        db.execute("UPDATE loans SET status = 'cancelled' WHERE id = ?", (loan_id,))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _hydrate(loans):
    current = now()
    for loan in loans:
        loan["requested_label"] = datetime_label(loan["requested_at"])
        loan["expected_label"] = datetime_label(loan["expected_return_at"])
        loan["confirmed_label"] = datetime_label(loan["confirmed_at"])
        loan["returned_label"] = datetime_label(loan["returned_at"])
        loan["overdue"] = (loan["status"] == "active" and
                           datetime.fromisoformat(loan["expected_return_at"]) < current)
    return loans


def get_dashboard():
    db = connect()
    try:
        # Pedidos pendentes não são limitados pelo estoque. Não oculte retiradas
        # ativas nem altere os contadores ao acumular novas solicitações.
        loans = rows(db.execute("SELECT * FROM loans WHERE status IN ('pending','active') ORDER BY id DESC"))
        for loan in loans:
            loan["devices"] = ", ".join(r["code"] for r in rows(db.execute("""
                SELECT d.code FROM loan_devices ld JOIN devices d ON d.id = ld.device_id
                WHERE ld.loan_id = ? ORDER BY d.id
            """, (loan["id"],))))
        loans = _hydrate(loans)
        available = len(rows(db.execute(AVAILABLE_SQL)))
        return {
            "available": available,
            "in_use": 20 - available,
            "pending_count": sum(l["status"] == "pending" for l in loans),
            "overdue_count": sum(l["overdue"] for l in loans),
            "pending": [l for l in loans if l["status"] == "pending"],
            "active": [l for l in loans if l["status"] == "active"],
        }
    finally:
        db.close()


def get_history():
    db = connect()
    try:
        loans = rows(db.execute("SELECT * FROM loans ORDER BY id DESC LIMIT 300"))
        for loan in loans:
            loan["devices"] = ", ".join(r["code"] for r in rows(db.execute("""
                SELECT d.code FROM loan_devices ld JOIN devices d ON d.id = ld.device_id
                WHERE ld.loan_id = ? ORDER BY d.id
            """, (loan["id"],))))
        return _hydrate(loans)
    finally:
        db.close()
