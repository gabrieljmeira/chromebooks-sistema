"""Operações da TI com revalidação transacional e auditoria antes/depois."""

import json
from datetime import datetime

import services as s
from database import connect, one, rows, transaction
from rooms import ROOMS


def reason(value):
    value = str(value or "").strip()
    if not 10 <= len(value) <= 500:
        raise s.ValidationError("Explique o motivo em 10 a 500 caracteres.")
    return value


def feature_repeat(db, token, fingerprint):
    if not isinstance(token, str) or not s.re.fullmatch(r"[A-Za-z0-9_-]{24,100}", token):
        raise s.ValidationError("Formulário inválido. Atualize a página.")
    previous = one(db.execute("SELECT * FROM feature_operations WHERE token=?", (token,)))
    if previous and previous["payload"] != fingerprint:
        raise s.ValidationError("Este formulário já foi utilizado. Atualize a página.")
    return previous is not None


def audit(db, action, detail, token, fingerprint):
    db.execute("INSERT INTO feature_operations VALUES (?,?,?)", (token, fingerprint, "ok"))
    db.execute("INSERT INTO management_audit(action,happened_at,actor,detail) VALUES (?,?,?,?)",
               (action, s.stamp(), s.actor.get(), json.dumps(detail, ensure_ascii=False, sort_keys=True)))


def inventory():
    db = connect()
    try:
        db.execute("BEGIN")
        devices = rows(db.execute("SELECT d.*,u.reason,u.changed_at, (SELECT a.loan_id FROM allocations a WHERE a.device_id=d.id AND a.returned_at IS NULL) AS loan_id FROM devices d LEFT JOIN unavailable_devices u ON d.id=u.device_id ORDER BY d.id"))
        events = rows(db.execute("SELECT * FROM management_audit WHERE action='manutencao' ORDER BY id DESC LIMIT 50"))
        for event in events:
            event["detail"] = json.loads(event["detail"])
            event["date"] = s.datetime_label(event["happened_at"])
        db.commit()
        return devices, events
    finally:
        db.close()


def set_unavailable(code, unavailable, explanation, token):
    code = s.codes([code])[0]
    explanation = reason(explanation)
    fingerprint = s.payload("maintenance", code, unavailable, explanation)
    with transaction() as db:
        if feature_repeat(db, token, fingerprint):
            return
        device_id = int(code[3:])
        previous = one(db.execute("SELECT * FROM unavailable_devices WHERE device_id=?", (device_id,)))
        if unavailable:
            if one(db.execute("SELECT id FROM allocations WHERE device_id=? AND returned_at IS NULL", (device_id,))):
                raise s.ValidationError("Registre o recebimento do aparelho antes de colocá-lo em manutenção.")
            db.execute("INSERT INTO unavailable_devices VALUES (?,?,?) ON CONFLICT(device_id) DO UPDATE SET reason=excluded.reason,changed_at=excluded.changed_at", (device_id, explanation, s.stamp()))
        else:
            if not previous:
                raise s.ValidationError("Este aparelho já está disponível.")
            db.execute("DELETE FROM unavailable_devices WHERE device_id=?", (device_id,))
        audit(db, "manutencao", {"code": code, "before": previous, "unavailable": unavailable, "reason": explanation}, token, fingerprint)


def edit_pending(loan_id, name, room, qty, start, expected, explanation, token, use_date=None):
    name, room = str(name or "").strip(), str(room or "").strip()
    qty, explanation = s.quantity(qty), reason(explanation)
    if not 3 <= len(name) <= 100 or room not in ROOMS:
        raise s.ValidationError("Informe o professor e uma sala da lista.")
    fingerprint = s.payload("edit", loan_id, name, room, qty, start, expected, explanation, use_date)
    with transaction() as db:
        if s.repeat(db, token, fingerprint) is not None:
            return
        loan = s.get_loan(db, loan_id)
        if loan["status"] != "pending":
            raise s.ValidationError("Somente pedidos ainda não entregues podem ser editados.")
        current = s.now()
        # Manter o início solicitado já passado é permitido; não recria o pedido.
        reference = current
        if use_date:
            from datetime import date, timedelta
            try:
                selected = date.fromisoformat(use_date)
            except (ValueError, TypeError):
                raise s.ValidationError("Informe uma data válida.")
            if not current.date() <= selected <= current.date() + timedelta(days=2):
                raise s.ValidationError("Escolha hoje, amanhã ou depois de amanhã.")
            reference = current.replace(year=selected.year, month=selected.month, day=selected.day)
        begin, end = s.clock(start, reference), s.clock(expected, reference)
        original = datetime.fromisoformat(loan["start_at"])
        if not use_date and original.date() != current.date():
            raise s.ValidationError("O pedido é de outro dia. Cancele-o e registre um novo pedido.")
        if begin < current and begin.replace(second=0,microsecond=0) != original.replace(second=0,microsecond=0):
            raise s.ValidationError("Para alterar o início, escolha um horário futuro de hoje.")
        if begin.replace(second=0,microsecond=0) == original.replace(second=0,microsecond=0):
            begin = original
        if end <= max(begin, current):
            raise s.ValidationError("A devolução deve ser posterior ao início e ao horário atual.")
        s.assert_room_available(db, room, max(begin, current), end, current, exclude=loan_id)
        if s.capacity(db, max(begin, current), end, current, exclude=loan_id) < qty:
            raise s.ValidationError("Não há aparelhos suficientes durante todo o novo intervalo.")
        after = {"professor_name": name, "room": room, "quantity": qty, "start_at": s.stamp(begin), "expected_return_at": s.stamp(end), "kind": "scheduled" if begin > current else "now"}
        db.execute("UPDATE loans SET professor_name=?,room=?,quantity=?,start_at=?,expected_return_at=?,kind=? WHERE id=?", (*after.values(), loan_id))
        s.record(db, token, fingerprint, loan_id, "edicao", {"before": {k: loan[k] for k in after}, "after": after, "reason": explanation})


def extend_loan(loan_id, expected, explanation, token):
    explanation = reason(explanation)
    fingerprint = s.payload("extend", loan_id, expected, explanation)
    with transaction() as db:
        if s.repeat(db, token, fingerprint) is not None:
            return
        loan = s.get_loan(db, loan_id)
        if loan["status"] != "active" or loan["needs_review"]:
            raise s.ValidationError("A prorrogação exige empréstimo em uso com códigos conferidos.")
        current = s.now()
        end = s.clock(expected, current)
        if end <= max(current, datetime.fromisoformat(loan["expected_return_at"])):
            raise s.ValidationError("Escolha um horário de hoje posterior ao atual e à previsão anterior.")
        count = one(db.execute("SELECT COUNT(*) AS n FROM allocations WHERE loan_id=? AND returned_at IS NULL", (loan_id,)))["n"]
        s.assert_room_available(db, loan["room"], current, end, current, exclude=loan_id)
        if s.capacity(db, current, end, current, exclude=loan_id) < count:
            raise s.ValidationError("A prorrogação prejudicaria outra reserva de aparelhos.")
        db.execute("UPDATE loans SET expected_return_at=? WHERE id=?", (s.stamp(end), loan_id))
        s.record(db, token, fingerprint, loan_id, "prorrogacao", {"before": {"expected_return_at": loan["expected_return_at"]}, "after": {"expected_return_at": s.stamp(end)}, "reason": explanation})


def correction_data(loan_id):
    db = connect()
    try:
        loan = s.get_loan(db, loan_id)
        allocations = rows(db.execute("SELECT a.*,d.code FROM allocations a JOIN devices d ON d.id=a.device_id WHERE loan_id=? ORDER BY a.id", (loan_id,)))
        return loan, allocations
    finally:
        db.close()


def correct_allocation(loan_id, allocation_id, code, state, explanation, token):
    code, explanation = s.codes([code])[0], reason(explanation)
    if state not in ("active", "returned"):
        raise s.ValidationError("Escolha a situação correta do aparelho.")
    fingerprint = s.payload("correct", loan_id, allocation_id, code, state, explanation)
    with transaction() as db:
        if s.repeat(db, token, fingerprint) is not None:
            return
        loan = s.get_loan(db, loan_id)
        if loan["needs_review"] or loan["status"] not in ("active", "returned"):
            raise s.ValidationError("A correção exige um empréstimo entregue e conferido.")
        allocation = one(db.execute("SELECT * FROM allocations WHERE id=? AND loan_id=?", (allocation_id, loan_id)))
        if not allocation:
            raise s.ValidationError("Movimentação não encontrada neste empréstimo.")
        current = s.now()
        device_id = int(code[3:])
        returned_at = (allocation["returned_at"] or s.stamp(current)) if state == "returned" else None
        if device_id == allocation["device_id"] and returned_at == allocation["returned_at"]:
            raise s.ValidationError("Nenhuma alteração informada.")
        other = rows(db.execute("SELECT * FROM allocations WHERE device_id=? AND id<>?", (device_id, allocation_id)))
        finish = datetime.fromisoformat(returned_at) if returned_at else None
        begin = datetime.fromisoformat(allocation["delivered_at"])
        for item in other:
            other_end = datetime.fromisoformat(item["returned_at"]) if item["returned_at"] else None
            other_begin = datetime.fromisoformat(item["delivered_at"])
            if (finish is None or other_begin < finish) and (other_end is None or begin < other_end):
                raise s.ValidationError("O código conflita com outra entrega neste período. Confira o histórico.")
            if item["loan_id"] == loan_id:
                raise s.ValidationError("Este código já está registrado no empréstimo.")
        if returned_at is None:
            if one(db.execute("SELECT device_id FROM unavailable_devices WHERE device_id=?", (device_id,))):
                raise s.ValidationError("Retire o aparelho da manutenção antes de corrigir para Em uso.")
            # Reabrir recebimento incorreto só é permitido sem conflito presente/futuro.
            end = max(current, datetime.fromisoformat(loan["expected_return_at"]))
            # Atraso é indeterminado: não pode consumir reservas futuras.
            if end <= current:
                end = current.replace(hour=23, minute=59, second=59, microsecond=999999)
            s.assert_room_available(db, loan["room"], current, end, current, exclude=loan_id)
            count = one(db.execute("SELECT COUNT(*) AS n FROM allocations WHERE loan_id=? AND returned_at IS NULL AND id<>?", (loan_id, allocation_id)))["n"] + 1
            if s.capacity(db, current, end, current, exclude=loan_id) < count:
                raise s.ValidationError("A reabertura prejudicaria outra reserva. Confira a situação física e os pedidos.")
        after = {"device_id": device_id, "returned_at": returned_at}
        db.execute("UPDATE allocations SET device_id=?,returned_at=? WHERE id=?", (device_id, returned_at, allocation_id))
        remaining = one(db.execute("SELECT COUNT(*) AS n FROM allocations WHERE loan_id=? AND returned_at IS NULL", (loan_id,)))["n"]
        last_return = one(db.execute("SELECT MAX(returned_at) AS moment FROM allocations WHERE loan_id=?", (loan_id,)))["moment"]
        db.execute("UPDATE loans SET status=?,returned_at=? WHERE id=?", ("active" if remaining else "returned", None if remaining else last_return, loan_id))
        s.record(db, token, fingerprint, loan_id, "correcao", {"allocation_id": allocation_id, "codes": [code], "before": {k: allocation[k] for k in after}, "after": after, "reason": explanation})
