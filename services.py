"""Pedidos e entregas pela TI. Todas as decisões de estoque são transacionais."""

import hashlib
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from database import connect, one, rows, transaction

TZ = ZoneInfo("America/Sao_Paulo")


class ValidationError(ValueError):
    pass


def now():
    return datetime.now(TZ)


def stamp(value=None):
    return (value or now()).isoformat(timespec="seconds")


def datetime_label(value):
    return (
        datetime.fromisoformat(value).astimezone(TZ).strftime("%d/%m/%Y %H:%M")
        if value
        else "—"
    )


def clock(raw, current):
    if not isinstance(raw, str) or not re.fullmatch(
        r"(?:[01][0-9]|2[0-3]):?[0-5][0-9]", raw
    ):
        raise ValidationError("Informe um horário válido (HH:MM).")
    digits = raw.replace(":", "")
    return current.replace(
        hour=int(digits[:2]), minute=int(digits[2:]), second=0, microsecond=0
    )


def quantity(raw):
    if not re.fullmatch(r"(?:[1-9]|1[0-9]|20)", str(raw)):
        raise ValidationError("A quantidade deve ser de 1 a 20.")
    return int(raw)


def codes(values):
    if not isinstance(values, (list, tuple)) or not values or len(values) > 20:
        raise ValidationError(
            "Selecione os aparelhos efetivamente entregues ou recebidos."
        )
    if any(
        not isinstance(c, str) or not re.fullmatch(r"CH-(?:00[1-9]|01[0-9]|020)", c)
        for c in values
    ):
        raise ValidationError("Código de aparelho inválido.")
    if len(values) != len(set(values)):
        raise ValidationError("Não repita códigos de aparelhos.")
    return sorted(values)


def payload(action, *args):
    return hashlib.sha256(
        json.dumps([action, *args], sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def repeat(db, token, fingerprint):
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9_-]{24,100}", token):
        raise ValidationError(
            "Identificador do formulário inválido. Atualize a página."
        )
    previous = one(db.execute("SELECT * FROM operations WHERE token=?", (token,)))
    if previous and previous["payload"] != fingerprint:
        raise ValidationError(
            "Este formulário já foi utilizado com outros dados. Atualize a página."
        )
    return previous["loan_id"] if previous else None


def record(db, token, fingerprint, loan_id, action, detail):
    db.execute("INSERT INTO operations VALUES (?,?,?)", (token, fingerprint, loan_id))
    db.execute(
        "INSERT INTO audit(loan_id,action,happened_at,detail) VALUES (?,?,?,?)",
        (
            loan_id,
            action,
            stamp(),
            json.dumps(detail, ensure_ascii=False, sort_keys=True),
        ),
    )


def get_loan(db, loan_id):
    loan = one(db.execute("SELECT * FROM loans WHERE id=?", (loan_id,)))
    if not loan:
        raise ValidationError("Pedido não encontrado.")
    return loan


def assert_reviewed(db):
    if one(
        db.execute(
            "SELECT id FROM loans WHERE status='active' AND needs_review=1 LIMIT 1"
        )
    ):
        raise ValidationError(
            "A TI precisa conferir os aparelhos dos empréstimos antigos antes de aceitar novos pedidos ou entregas."
        )


def capacity(db, start, end, current, exclude=None):
    """Capacidade mínima em [início,fim); atrasados ocupam todo intervalo futuro."""
    assert_reviewed(db)
    events = []
    loans = rows(db.execute("""SELECT l.*, (SELECT COUNT(*) FROM allocations a
        WHERE a.loan_id=l.id AND a.returned_at IS NULL) AS outstanding
        FROM loans l WHERE status IN ('pending','active')"""))
    for loan in loans:
        if loan["id"] == exclude:
            continue
        a = datetime.fromisoformat(loan["start_at"])
        b = datetime.fromisoformat(loan["expected_return_at"])
        qty = loan["quantity"] if loan["status"] == "pending" else loan["outstanding"]
        if loan["status"] == "active":
            a = min(current, a)
            if b <= current:
                b = end  # atrasados não têm uma liberação presumida
        a = max(a, start)
        b = min(b, end)
        if a < b and qty:
            events.extend([(a, qty), (b, -qty)])
    used = peak = 0
    for _, delta in sorted(events, key=lambda e: (e[0], e[1])):
        used += delta
        peak = max(peak, used)
    return 20 - peak


def request_loan(name, room, qty, expected, kind="now", start=None, token=None):
    name = str(name or "").strip()
    room = str(room or "").strip()
    if not 3 <= len(name) <= 100 or not 1 <= len(room) <= 40:
        raise ValidationError(
            "Informe nome (3 a 100 caracteres) e sala (1 a 40 caracteres)."
        )
    qty = quantity(qty)
    if kind not in ("now", "scheduled"):
        raise ValidationError("Escolha Pedir agora ou Agendar entrega.")
    fingerprint = payload(
        "request",
        name,
        room,
        qty,
        expected,
        kind,
        start if kind == "scheduled" else None,
    )
    with transaction() as db:
        previous = repeat(db, token, fingerprint)
        if previous is not None:
            return previous
        current = now()
        end = clock(expected, current)
        begin = current if kind == "now" else clock(start, current)
        if kind == "scheduled" and begin <= current:
            raise ValidationError("Agende a entrega para um horário futuro de hoje.")
        if end <= begin:
            raise ValidationError(
                "A devolução de hoje deve ser posterior ao início do pedido."
            )
        if capacity(db, begin, end, current) < qty:
            raise ValidationError(
                "Não há essa quantidade disponível durante todo o intervalo solicitado."
            )
        db.execute(
            """INSERT INTO loans(professor_name,room,quantity,requested_at,expected_return_at,
            start_at,kind,status,needs_review) VALUES (?,?,?,?,?,?,?,'pending',0)""",
            (name, room, qty, stamp(current), stamp(end), stamp(begin), kind),
        )
        loan_id = int(one(db.execute("SELECT last_insert_rowid() AS id"))["id"])
        record(
            db,
            token,
            fingerprint,
            loan_id,
            "pedido",
            {"kind": kind, "start": stamp(begin), "end": stamp(end), "quantity": qty},
        )
        return loan_id


def deliver_loan(loan_id, selected, token):
    selected = codes(selected)
    fingerprint = payload("deliver", loan_id, selected)
    with transaction() as db:
        if repeat(db, token, fingerprint) is not None:
            return
        loan = get_loan(db, loan_id)
        current = now()
        if loan["status"] != "pending":
            raise ValidationError("Este pedido não está aguardando entrega.")
        if len(selected) != loan["quantity"]:
            raise ValidationError("Selecione exatamente a quantidade do pedido.")
        end = datetime.fromisoformat(loan["expected_return_at"])
        if end <= current:
            raise ValidationError(
                "A previsão de devolução passou. Cancele o pedido e registre outro."
            )
        if capacity(db, current, end, current, exclude=loan_id) < len(selected):
            raise ValidationError(
                "Esta entrega conflita com outros pedidos ou reservas."
            )
        occupied = {
            r["code"] for r in rows(db.execute("""SELECT d.code FROM allocations a
            JOIN devices d ON d.id=a.device_id WHERE a.returned_at IS NULL"""))
        }
        if occupied.intersection(selected):
            raise ValidationError(
                "Um dos aparelhos selecionados já está emprestado. Atualize o painel."
            )
        for code in selected:
            db.execute(
                "INSERT INTO allocations(loan_id,device_id,delivered_at) VALUES (?,?,?)",
                (loan_id, int(code[3:]), stamp(current)),
            )
        db.execute(
            "UPDATE loans SET status='active',confirmed_at=?,start_at=? WHERE id=?",
            (stamp(current), stamp(current), loan_id),
        )
        record(
            db,
            token,
            fingerprint,
            loan_id,
            "entrega",
            {"codes": selected, "planned_start": loan["start_at"]},
        )


def return_loan(loan_id, selected, token):
    selected = codes(selected)
    fingerprint = payload("return", loan_id, selected)
    with transaction() as db:
        if repeat(db, token, fingerprint) is not None:
            return
        loan = get_loan(db, loan_id)
        if loan["status"] != "active" or loan["needs_review"]:
            raise ValidationError(
                "A devolução exige um empréstimo ativo com códigos conferidos."
            )
        remaining = {
            r["device_id"]
            for r in rows(
                db.execute(
                    "SELECT device_id FROM allocations WHERE loan_id=? AND returned_at IS NULL",
                    (loan_id,),
                )
            )
        }
        chosen = {int(c[3:]) for c in selected}
        if not chosen <= remaining:
            raise ValidationError(
                "Selecione somente aparelhos ainda emprestados neste pedido."
            )
        moment = stamp()
        for device_id in chosen:
            db.execute(
                "UPDATE allocations SET returned_at=? WHERE loan_id=? AND device_id=? AND returned_at IS NULL",
                (moment, loan_id, device_id),
            )
        if chosen == remaining:
            db.execute(
                "UPDATE loans SET status='returned',returned_at=? WHERE id=?",
                (moment, loan_id),
            )
        record(db, token, fingerprint, loan_id, "devolucao", {"codes": selected})


def cancel_loan(loan_id, token):
    fingerprint = payload("cancel", loan_id)
    with transaction() as db:
        if repeat(db, token, fingerprint) is not None:
            return
        loan = get_loan(db, loan_id)
        if loan["status"] != "pending":
            raise ValidationError(
                "Somente pedidos ainda não entregues podem ser cancelados."
            )
        db.execute("UPDATE loans SET status='cancelled' WHERE id=?", (loan_id,))
        record(db, token, fingerprint, loan_id, "cancelamento", {})


def reconcile_loan(loan_id, selected, reason, token):
    selected = codes(selected)
    reason = str(reason or "").strip()
    if not 10 <= len(reason) <= 500:
        raise ValidationError("Explique a conferência em 10 a 500 caracteres.")
    fingerprint = payload("review", loan_id, selected, reason)
    with transaction() as db:
        if repeat(db, token, fingerprint) is not None:
            return
        loan = get_loan(db, loan_id)
        if not loan["needs_review"] or loan["status"] not in ("active", "returned"):
            raise ValidationError(
                "Este registro não precisa de conferência de códigos antigos."
            )
        original = rows(
            db.execute(
                "SELECT * FROM loan_devices WHERE loan_id=? ORDER BY device_id",
                (loan_id,),
            )
        )
        required = (
            loan["quantity"]
            if loan["status"] == "returned"
            else loan["quantity"] - sum(bool(r["returned_at"]) for r in original)
        )
        if len(selected) != required:
            raise ValidationError(
                f"Selecione {required} aparelhos para esta conferência."
            )
        if loan["status"] == "active":
            busy = {
                r["device_id"]
                for r in rows(
                    db.execute(
                        "SELECT device_id FROM allocations WHERE returned_at IS NULL"
                    )
                )
            }
            if busy.intersection(int(c[3:]) for c in selected):
                raise ValidationError(
                    "Um código informado já pertence a outro empréstimo conferido."
                )
        if not loan["confirmed_at"] or (
            loan["status"] == "returned" and not loan["returned_at"]
        ):
            raise ValidationError(
                "O registro antigo está sem horário de entrega ou devolução. Preserve o backup e revise o histórico antes de conferir os códigos."
            )
        for code in selected:
            db.execute(
                "INSERT INTO allocations(loan_id,device_id,delivered_at,returned_at) VALUES (?,?,?,?)",
                (
                    loan_id,
                    int(code[3:]),
                    loan["confirmed_at"],
                    (loan["returned_at"] if loan["status"] == "returned" else None),
                ),
            )
        db.execute("UPDATE loans SET needs_review=0 WHERE id=?", (loan_id,))
        record(
            db,
            token,
            fingerprint,
            loan_id,
            "conferencia_legado",
            {
                "reason": reason,
                "original": original,
                "verified_codes": selected,
                "scope": "em uso" if loan["status"] == "active" else "histórico",
            },
        )


def snapshot(history=False):
    db = connect()
    try:
        # Uma leitura consistente mantém contadores e listas da mesma versão do banco.
        db.execute("BEGIN")
        sql = (
            "SELECT * FROM loans WHERE id IN (SELECT id FROM loans ORDER BY id DESC LIMIT 300) OR (needs_review=1 AND status='active') ORDER BY id DESC"
            if history
            else "SELECT * FROM loans WHERE status IN ('pending','active') ORDER BY start_at,id"
        )
        loans = rows(db.execute(sql))
        ids = {l["id"] for l in loans}
        marks = ",".join("?" for _ in ids) or "NULL"
        allocations = rows(
            db.execute(
                f"SELECT a.*,d.code FROM allocations a JOIN devices d ON d.id=a.device_id WHERE a.loan_id IN ({marks}) ORDER BY d.id",
                tuple(ids),
            )
        )
        legacy = rows(
            db.execute(
                f"SELECT ld.*,d.code FROM loan_devices ld JOIN devices d ON d.id=ld.device_id WHERE ld.loan_id IN ({marks}) ORDER BY d.id",
                tuple(ids),
            )
        )
        current = now()
        for loan in loans:
            loan["devices"] = [a for a in allocations if a["loan_id"] == loan["id"]]
            loan["outstanding"] = [
                a for a in loan["devices"] if a["returned_at"] is None
            ]
            loan["legacy"] = [a for a in legacy if a["loan_id"] == loan["id"]]
            loan["remaining"] = (
                loan["quantity"] - sum(bool(a["returned_at"]) for a in loan["legacy"])
                if loan["needs_review"] and loan["status"] == "active"
                else len(loan["outstanding"])
            )
            loan["overdue"] = (
                loan["status"] == "active"
                and loan["remaining"] > 0
                and datetime.fromisoformat(loan["expected_return_at"]) <= current
            )
            for field in (
                "start_at",
                "expected_return_at",
                "confirmed_at",
                "returned_at",
            ):
                loan[field + "_label"] = datetime_label(loan[field])
        occupied = {
            a["device_id"]
            for a in rows(
                db.execute(
                    "SELECT device_id FROM allocations WHERE returned_at IS NULL"
                )
            )
        }
        blocked = bool(
            one(
                db.execute(
                    "SELECT id FROM loans WHERE status='active' AND needs_review=1 LIMIT 1"
                )
            )
        )
        free = rows(db.execute("SELECT * FROM devices ORDER BY id"))
        free = [d for d in free if d["id"] not in occupied]
        audit = (
            rows(
                db.execute(
                    f"SELECT * FROM audit WHERE loan_id IN ({marks}) ORDER BY id DESC",
                    tuple(ids),
                )
            )
            if history
            else []
        )
        db.commit()
        return {
            "loans": loans,
            "pending": [l for l in loans if l["status"] == "pending"],
            "active": [l for l in loans if l["status"] == "active"],
            "free": free,
            "available": 0 if blocked else len(free),
            "blocked": blocked,
            "server_time": stamp(current),
            "audit": [a for a in audit if a["loan_id"] in ids],
        }
    finally:
        db.close()


def get_dashboard():
    return snapshot()


def get_history():
    return snapshot(True)


def stock_count():
    return snapshot()["available"]


def rate_limit(key, limit, seconds):
    import time

    current = int(time.time())
    end = (current // seconds + 1) * seconds
    with transaction() as db:
        db.execute("DELETE FROM rate_limits WHERE expires<=?", (current,))
        entry = one(db.execute("SELECT hits FROM rate_limits WHERE key=?", (key,)))
        if entry and entry["hits"] >= limit:
            return False
        db.execute(
            """INSERT INTO rate_limits(key,hits,expires) VALUES (?,1,?)
            ON CONFLICT(key) DO UPDATE SET hits=hits+1""",
            (key, end),
        )
    return True
