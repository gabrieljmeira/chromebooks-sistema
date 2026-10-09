"""Regras de negócio, sem dependência de Flask."""
from __future__ import annotations

from datetime import datetime
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


def _parse_expected(raw, current):
    try:
        expected = datetime.strptime(raw, "%H:%M").replace(
            year=current.year, month=current.month, day=current.day, tzinfo=TZ,
        )
    except (ValueError, TypeError):
        raise ValidationError("Informe um horário válido para a devolução.")
    if expected <= current:
        raise ValidationError("A devolução prevista deve ser em um horário futuro de hoje.")
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
    db = connect()
    try:
        # Registro e estoque mudam juntos; duas retiradas não usam o mesmo saldo.
        _transaction(db)
        current = now()
        expected = _parse_expected(expected_raw, current)
        free = rows(db.execute(AVAILABLE_SQL))
        if qty > len(free):
            raise ValidationError("Não há essa quantidade disponível no momento.")
        taken_at = current.isoformat(timespec="seconds")
        # Mantém as colunas existentes para preservar bancos e históricos antigos.
        db.execute("""
            INSERT INTO loans (
                professor_name, room, quantity, requested_at,
                expected_return_at, confirmed_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, 'active')
        """, (name, room, qty, taken_at, expected.isoformat(timespec="seconds"), taken_at))
        new_id = one(db.execute("SELECT last_insert_rowid() AS id"))["id"]
        for device in free[:qty]:
            db.execute("INSERT INTO loan_devices (loan_id, device_id) VALUES (?, ?)", (new_id, device["id"]))
        db.commit()
        return int(new_id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _transaction(db):
    # Serializa alterações de estoque no SQLite. Turso remoto requer validação.
    db.execute("BEGIN IMMEDIATE")


def return_loan(loan_id, quantity):
    db = connect()
    try:
        _transaction(db)
        loan = one(db.execute("SELECT status FROM loans WHERE id = ?", (loan_id,)))
        if not loan or loan["status"] != "active":
            raise ValidationError("Somente retiradas ativas podem ser devolvidas.")
        try:
            qty = int(quantity)
        except (ValueError, TypeError):
            raise ValidationError("Informe quantos Chromebooks foram devolvidos.")
        if str(quantity) != str(qty) or qty < 1:
            raise ValidationError("A quantidade devolvida precisa ser um número inteiro maior que zero.")
        outstanding = rows(db.execute("""
            SELECT device_id FROM loan_devices
            WHERE loan_id = ? AND returned_at IS NULL ORDER BY device_id
        """, (loan_id,)))
        if qty > len(outstanding):
            raise ValidationError("A quantidade devolvida não pode superar os equipamentos ainda em uso neste registro.")
        returned_at = now().isoformat(timespec="seconds")
        for device in outstanding[:qty]:
            db.execute("""
                UPDATE loan_devices SET returned_at = ?
                WHERE loan_id = ? AND device_id = ? AND returned_at IS NULL
            """, (returned_at, loan_id, device["device_id"]))
        if qty == len(outstanding):
            db.execute("""
                UPDATE loans SET status = 'returned', returned_at = ?
                WHERE id = ? AND status = 'active'
            """, (returned_at, loan_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _hydrate(loans):
    current = now()
    for loan in loans:
        loan["expected_label"] = datetime_label(loan["expected_return_at"])
        loan["taken_label"] = datetime_label(loan["confirmed_at"])
        loan["returned_label"] = datetime_label(loan["returned_at"])
        loan["overdue"] = (loan["status"] == "active" and
                           datetime.fromisoformat(loan["expected_return_at"]) < current)
    return loans


def _attach_devices(db, loans):
    for loan in loans:
        devices = rows(db.execute("""
            SELECT d.code, ld.returned_at FROM loan_devices ld
            JOIN devices d ON d.id = ld.device_id
            WHERE ld.loan_id = ? ORDER BY d.id
        """, (loan["id"],)))
        outstanding = [d for d in devices if not d["returned_at"] and loan["status"] == "active"]
        loan["devices"] = ", ".join(d["code"] for d in devices)
        loan["outstanding_devices"] = ", ".join(d["code"] for d in outstanding)
        loan["remaining_quantity"] = len(outstanding)
        loan["returned_quantity"] = sum(bool(d["returned_at"]) for d in devices)
    return _hydrate(loans)


def get_dashboard():
    db = connect()
    try:
        loans = rows(db.execute("SELECT * FROM loans WHERE status = 'active' ORDER BY id DESC"))
        loans = _attach_devices(db, loans)
        available = len(rows(db.execute(AVAILABLE_SQL)))
        return {
            "available": available,
            "in_use": 20 - available,
            "overdue_count": sum(l["overdue"] for l in loans),
            "active": loans,
        }
    finally:
        db.close()


def get_history():
    db = connect()
    try:
        loans = rows(db.execute("SELECT * FROM loans ORDER BY id DESC LIMIT 300"))
        return _attach_devices(db, loans)
    finally:
        db.close()
