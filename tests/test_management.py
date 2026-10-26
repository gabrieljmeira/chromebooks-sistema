import json
import secrets
import sqlite3
from datetime import timedelta

import pytest
import accounts
import backups
import management as m
import services as s
from database import connect, rows, one, init_db
from test_app import login, fields


def token():
    return secrets.token_urlsafe(32)


WHY = "Conferência física realizada pela equipe da TI."


def loan(room="101", qty=1, start=None, end="12:00"):
    return s.request_loan("Professora Ana", room, qty, end, "scheduled" if start else "now", start, token())


def allocations(loan_id):
    return m.correction_data(loan_id)[1]


def test_maintenance_reduces_stock_and_reservations_idempotently():
    key = token()
    m.set_unavailable("CH-001", True, WHY, key)
    m.set_unavailable("CH-001", True, WHY, key)
    assert s.stock_count() == 19
    with pytest.raises(s.ValidationError, match="quantidade"):
        loan(qty=20)
    a = loan(qty=19)
    with pytest.raises(s.ValidationError, match="manutenção"):
        s.deliver_loan(a, [f"CH-{i:03}" for i in range(1,20)], token())
    m.set_unavailable("CH-001", False, WHY, token())
    assert s.stock_count() == 20
    assert len(m.inventory()[1]) == 2


def test_maintenance_on_loan_rejected_and_existing_shortage_visible():
    a = loan(qty=20)
    m.set_unavailable("CH-001", True, WHY, token())
    assert s.get_dashboard()["shortages"] == [a]
    m.set_unavailable("CH-001", False, WHY, token())
    s.deliver_loan(a, [f"CH-{i:03}" for i in range(1,21)], token())
    with pytest.raises(s.ValidationError, match="recebimento"):
        m.set_unavailable("CH-001", True, WHY, token())


def test_edit_revalidates_room_capacity_and_preserves_original_audit():
    a, b = loan(), loan("103", qty=19)
    with pytest.raises(s.ValidationError, match="SALA EM USO"):
        m.edit_pending(a, "Professor Bruno", "103", 1, "10:00", "12:30", WHY, token())
    with pytest.raises(s.ValidationError, match="suficientes"):
        m.edit_pending(a, "Professor Bruno", "105", 2, "10:00", "12:00", WHY, token())
    key = token()
    m.edit_pending(a, "Professor Bruno", "105", 1, "10:00", "12:00", WHY, key)
    m.edit_pending(a, "Professor Bruno", "105", 1, "10:00", "12:00", WHY, key)
    data = s.get_history()
    assert next(item for item in data["loans"] if item["id"]==a)["room"] == "105"
    changes = [e for e in data["audit"] if e["action"]=="edicao"]
    assert len(changes)==1 and json.loads(changes[0]["detail"])["before"]["room"]=="101"
    assert any(e["action"]=="pedido" and e["loan_id"]==a for e in data["audit"])


def test_edit_never_changes_delivered_or_another_day(monkeypatch):
    a = loan()
    s.deliver_loan(a, ["CH-001"], token())
    with pytest.raises(s.ValidationError):
        m.edit_pending(a,"Prof. Ana","105",1,"11:00","12:00",WHY,token())
    b = loan("103")
    tomorrow = s.now()+timedelta(days=1)
    monkeypatch.setattr(s,"now",lambda:tomorrow)
    with pytest.raises(s.ValidationError,match="outro dia"):
        m.edit_pending(b,"Prof. Ana","105",1,"11:00","12:00",WHY,token())


def test_extend_conflicts_then_succeeds_and_audits():
    a = loan(qty=2)
    s.deliver_loan(a,["CH-001","CH-002"],token())
    b = loan(start="12:00", end="13:00")
    with pytest.raises(s.ValidationError,match="SALA EM USO"):
        m.extend_loan(a,"12:30",WHY,token())
    s.cancel_loan(b,token())
    c = loan("103",qty=19,start="12:00",end="13:00")
    with pytest.raises(s.ValidationError,match="reserva"):
        m.extend_loan(a,"12:30",WHY,token())
    s.return_loan(a,["CH-002"],token())
    key=token()
    m.extend_loan(a,"12:30",WHY,key)
    m.extend_loan(a,"12:30",WHY,key)
    assert allocations(a)[1]["returned_at"]
    assert m.correction_data(a)[0]["expected_return_at"][11:16]=="12:30"


def test_correction_code_and_receipt_keeps_original_events():
    a = loan()
    s.deliver_loan(a,["CH-001"],token())
    item=allocations(a)[0]
    key=token()
    m.correct_allocation(a,item["id"],"CH-004","active",WHY,key)
    m.correct_allocation(a,item["id"],"CH-004","active",WHY,key)
    assert allocations(a)[0]["code"]=="CH-004"
    s.return_loan(a,["CH-004"],token())
    assert m.correction_data(a)[0]["status"]=="returned"
    m.correct_allocation(a,item["id"],"CH-004","active",WHY,token())
    assert s.stock_count()==19
    assert m.correction_data(a)[0]["status"]=="active"
    original=next(e for e in s.get_history()["audit"] if e["action"]=="entrega")
    assert json.loads(original["detail"])["codes"]==["CH-001"]
    corrections=[e for e in s.get_history()["audit"] if e["action"]=="correcao"]
    assert len(corrections)==2
    assert any(json.loads(e["detail"])["before"]["returned_at"] for e in corrections)


def test_correction_refuses_busy_code_maintenance_and_other_loan_record():
    a,b=loan(),loan("103")
    s.deliver_loan(a,["CH-001"],token())
    s.deliver_loan(b,["CH-002"],token())
    item=allocations(a)[0]
    with pytest.raises(s.ValidationError,match="conflita"):
        m.correct_allocation(a,item["id"],"CH-002","active",WHY,token())
    with pytest.raises(s.ValidationError,match="encontrada"):
        m.correct_allocation(a,allocations(b)[0]["id"],"CH-003","active",WHY,token())
    m.set_unavailable("CH-003",True,WHY,token())
    with pytest.raises(s.ValidationError,match="manutenção"):
        m.correct_allocation(a,item["id"],"CH-003","active",WHY,token())


def test_reopen_return_cannot_overbook_or_take_reserved_room():
    a=loan(qty=2)
    s.deliver_loan(a,["CH-001","CH-002"],token())
    s.return_loan(a,["CH-001","CH-002"],token())
    loan("103",qty=20)
    with pytest.raises(s.ValidationError,match="reserva"):
        m.correct_allocation(a,allocations(a)[0]["id"],"CH-001","active",WHY,token())


def test_management_forms_and_diagnostics(client):
    a=loan()
    page = login(client)
    assert b">Contas<" not in page.data
    assert client.get("/admin/contas").status_code == 404
    assert client.post("/admin/contas", data=fields(page, "/admin/logout")).status_code == 404
    for path in ("/admin/inventario",f"/admin/pedido/{a}/editar"):
        assert client.get(path).status_code==200
    path=f"/admin/pedido/{a}/editar"
    data=fields(client.get(path))
    data.update(name="Prof. Bruno",room="105",quantity="1",start_time="10:00",expected_return="12:30",reason=WHY)
    assert client.post(path,data=data).status_code==303
    assert m.correction_data(a)[0]["room"]=="105"
    assert client.get("/saude").json=={"status":"ok"}


def test_database_configuration_failure_is_503_without_secrets(client,monkeypatch):
    monkeypatch.setenv("VERCEL","1")
    response=client.get("/admin/login")
    assert response.status_code==503
    assert b"TURSO_DATABASE_URL" in response.data
    assert client.get("/saude").status_code==503


def user_login(client, username, password):
    data=fields(client.get("/admin/login"))
    data.update(username=username,password=password)
    return client.post("/admin/login",data=data)


def test_existing_individual_access_and_audit_remain_compatible(client):
    login(client)
    assert client.get("/admin/contas").status_code == 404
    accounts.create_user("gabriel","senha-individual-teste","manager",token())
    assert client.get("/admin/estado").status_code==401
    assert user_login(client,"","senha-exclusiva-teste").status_code==401
    assert user_login(client,"gabriel","senha-individual-teste").status_code==303
    assert client.get("/admin/diagnostico").status_code == 404
    a=loan()
    action=f"/admin/entregar/{a}"
    data=fields(client.get("/admin"),action)
    data["devices"]="CH-001"
    client.post(action,data=data)
    event=next(e for e in s.get_history()["audit"] if e["action"]=="entrega")
    assert event["actor"]=="gabriel"
    assert b"scrypt:" not in client.get("/admin/contas").data


def test_roles_session_revocation_and_last_manager(client):
    accounts.create_user("gestor","senha-gestor-teste","manager",token())
    accounts.create_user("tecnico","senha-tecnico-teste","technician",token())
    manager, technician=accounts.list_users()
    assert user_login(client,"tecnico","senha-tecnico-teste").status_code==303
    assert client.get("/admin/inventario").status_code==200
    assert client.get("/admin/contas").status_code==403
    assert client.get("/admin/diagnostico").status_code==403
    with client.session_transaction() as session:
        csrf=session["csrf"]
    assert client.post("/admin/backup",data={"csrf":csrf}).status_code==403
    assert client.get("/admin/exportar.csv").status_code==200
    accounts.update_user(technician["id"],"technician",False,"",token())
    assert client.get("/admin/estado").status_code==401
    with pytest.raises(s.ValidationError,match="gestor ativo"):
        accounts.update_user(manager["id"],"technician",False,"",token())


def test_individual_password_change_revokes_sessions(client):
    accounts.create_user("gestor","senha-gestor-teste","manager",token())
    user_login(client,"gestor","senha-gestor-teste")
    data=fields(client.get("/admin/minha-senha"))
    data.update(old_password="senha-gestor-teste",password="outra-senha-gestor")
    assert client.post("/admin/minha-senha",data=data).status_code==303
    assert client.get("/admin/estado").status_code==401
    assert user_login(client,"gestor","outra-senha-gestor").status_code==303


def test_csv_exports_all_filtered_rows_and_neutralizes_formulas(client):
    db=connect()
    try:
        for n in range(65):
            db.execute("INSERT INTO loans(professor_name,room,quantity,requested_at,start_at,expected_return_at,status) VALUES (?,?,?,?,?,?,'cancelled')",("=HYPERLINK(test)","101",1,s.stamp(),s.stamp(),s.stamp()))
    finally:
        db.close()
    login(client)
    response=client.get("/admin/exportar.csv?room=101&status=cancelled")
    text=response.data.decode("utf-8-sig")
    assert len(text.splitlines())==66
    assert "'=HYPERLINK(test)" in text
    assert client.get("/admin/exportar.csv?room=103").data.count(b"\n")==1


def test_backup_restore_roundtrip_preserves_accounts_audit_and_inventory(tmp_path):
    accounts.create_user("gestor","senha-gestor-teste","manager",token())
    a=loan()
    s.deliver_loan(a,["CH-004"],token())
    m.set_unavailable("CH-020",True,WHY,token())
    source=backups.write_private(tmp_path/"test.backup.json")
    target=backups.restore(source,tmp_path/"restored.sqlite")
    restored=sqlite3.connect(target)
    restored.row_factory=sqlite3.Row
    expected=json.loads(source.read_text())["tables"]
    for table in backups.TABLES:
        assert [dict(r) for r in restored.execute(f"SELECT * FROM {table}")]==expected[table]
    assert restored.execute("PRAGMA foreign_key_check").fetchall()==[]
    restored.close()
    with pytest.raises(ValueError,match="já existe"):
        backups.restore(source,target)
    with pytest.raises(FileExistsError):
        backups.write_private(source)


def test_corrupt_backup_is_rejected_without_publishing_destination(tmp_path):
    source=backups.write_private(tmp_path/"test.backup.json")
    content=json.loads(source.read_text())
    content["tables"]["devices"][0]["code"]="ERRADO"
    source.write_text(json.dumps(content))
    target=tmp_path/"restore.sqlite"
    with pytest.raises(ValueError,match="Inventário"):
        backups.restore(source,target)
    assert not target.exists()


def test_system_and_web_backup_removed(client):
    page = login(client)
    assert b">Sistema<" not in page.data
    assert client.get("/admin/diagnostico").status_code == 404
    assert client.post("/admin/backup", data=fields(page, "/admin/logout")).status_code == 404


def test_delivery_feed_uses_current_planned_time(client):
    a=loan(start="11:00")
    login(client)
    data=client.get("/admin/estado").json
    assert data["deliveries"][0]["start"][11:16]=="11:00"
    m.edit_pending(a,"Prof. Ana","101",1,"11:30","12:30",WHY,token())
    assert client.get("/admin/estado").json["deliveries"][0]["start"][11:16]=="11:30"
    s.cancel_loan(a,token())
    assert client.get("/admin/estado").json["deliveries"]==[]
