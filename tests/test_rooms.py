"""Regras de sala independentes da quantidade disponível de Chromebooks."""
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
import services as s
from database import connect, init_db, rows
from rooms import ROOMS


def token():
    return secrets.token_urlsafe(32)


def ask(room='210', start='11:00', end='12:00', kind='scheduled', qty=1, key=None):
    return s.request_loan('Professor teste', room, qty, end, kind, start, key or token())


def test_exact_school_catalog():
    assert ROOMS == ('101','103','105','106','107','108','109','111','113','114','115','116',
                     '201','202','203','205','206','207','208','209','210','211','212','213','215')
    ask('210')


@pytest.mark.parametrize('room', ['2010', '102', '204', '214', '', None, 'Sala 101', '101 OR 1=1'])
def test_unlisted_room_rejected(room):
    with pytest.raises(s.ValidationError, match='sala da lista'):
        ask(room)
    assert s.get_history()['loans'] == []


@pytest.mark.parametrize('start,end,allowed', [
    ('10:30','11:00',True), ('12:00','13:00',True), ('10:30','11:01',False),
    ('11:59','13:00',False), ('11:00','12:00',False), ('10:30','13:00',False),
    ('11:15','11:45',False),
])
def test_room_interval_boundaries(start, end, allowed):
    ask()
    if allowed:
        ask(start=start,end=end)
    else:
        with pytest.raises(s.ValidationError, match='SALA EM USO'):
            ask(start=start,end=end)
        assert len(s.get_history()['loans']) == 1


def test_different_rooms_can_overlap():
    ask('101')
    ask('103')
    assert len(s.get_dashboard()['pending']) == 2


def test_now_reserves_room_and_duplicate_token_is_safe():
    key = token()
    loan = ask(kind='now', key=key)
    assert ask(kind='now', key=key) == loan
    with pytest.raises(s.ValidationError, match='SALA EM USO'):
        ask(kind='now')
    with pytest.raises(s.ValidationError, match='SALA EM USO'):
        ask(start='10:30')
    ask(start='12:00', end='13:00')


def test_cancel_and_expired_pending_release_room(monkeypatch):
    loan = ask()
    s.cancel_loan(loan, token())
    ask()
    moment = s.now().replace(hour=13)
    monkeypatch.setattr(s,'now',lambda:moment)
    ask(kind='now',end='14:00')


def test_partial_return_keeps_room_full_return_releases():
    loan = ask(kind='now',qty=2)
    s.deliver_loan(loan,['CH-001','CH-002'],token())
    s.return_loan(loan,['CH-001'],token())
    with pytest.raises(s.ValidationError,match='SALA EM USO'):
        ask(kind='now')
    s.return_loan(loan,['CH-002'],token())
    ask(kind='now')


def test_overdue_blocks_future_requests_and_existing_delivery(monkeypatch):
    first = ask(kind='now',end='11:00')
    s.deliver_loan(first,['CH-001'],token())
    second = ask(start='11:00')
    moment = s.now().replace(hour=11)
    monkeypatch.setattr(s,'now',lambda:moment)
    with pytest.raises(s.ValidationError,match='SALA EM USO'):
        ask(start='15:00',end='16:00')
    with pytest.raises(s.ValidationError,match='SALA EM USO'):
        s.deliver_loan(second,['CH-002'],token())
    assert s.stock_count() == 19
    s.return_loan(first,['CH-001'],token())
    s.deliver_loan(second,['CH-002'],token())


def test_early_delivery_checks_room_and_preserves_requested_start():
    first = ask(kind='now',end='11:00')
    later = ask(start='11:00')
    with pytest.raises(s.ValidationError,match='SALA EM USO'):
        s.deliver_loan(later,['CH-002'],token())
    s.cancel_loan(first,token())
    s.deliver_loan(later,['CH-002'],token())
    loan = next(l for l in s.get_history()['loans'] if l['id']==later)
    assert loan['start_at'].endswith('11:00:00-03:00')
    assert loan['confirmed_at'].endswith('10:00:00-03:00')
    with pytest.raises(s.ValidationError,match='SALA EM USO'):
        ask(kind='now',end='10:30')


def test_concurrent_same_room_has_one_winner():
    def attempt(_):
        try:
            ask(qty=1)
            return True
        except s.ValidationError as exc:
            assert 'SALA EM USO' in str(exc)
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt,range(2))) == [False,True]
    assert len(s.get_history()['loans']) == 1


def test_existing_room_records_preserved_by_initialization():
    loan = ask()
    db = connect()
    db.execute("UPDATE loans SET room='Sala antiga' WHERE id=?",(loan,))
    before = rows(db.execute('SELECT * FROM loans'))
    db.close()
    init_db()
    db = connect()
    assert rows(db.execute('SELECT * FROM loans')) == before
    db.close()


def test_availability_private_details_never_exposed(client):
    ask()
    response = client.get('/salas/disponibilidade?kind=scheduled&start_time=11:30&expected_return=12:30')
    assert response.status_code == 200
    assert response.json['busy'] == ['210']
    assert set(response.json) == {'busy','start','end'}
    assert 'Professor' not in response.get_data(as_text=True)
    assert 'no-store' in response.headers['Cache-Control']
    assert client.get('/salas/disponibilidade?expected_return=25:00').status_code == 422
    assert client.get('/salas/disponibilidade?kind=scheduled&start_time=12:00&expected_return=13:00').json['busy'] == []


def test_public_form_lists_rooms_and_rejects_conflict_without_js(client):
    from test_app import public_data
    page = client.get('/retirada').get_data(as_text=True)
    assert '<select id="room"' in page and 'value="210"' in page and 'value="2010"' not in page
    first = public_data(client,room='210')
    assert client.post('/retirada',data=first).status_code == 303
    second = public_data(client,room='210')
    response = client.post('/retirada',data=second)
    assert response.status_code == 422
    assert 'SALA EM USO' in response.get_data(as_text=True)
    second['room'] = '2010'
    assert client.post('/retirada',data=second).status_code == 422
    second['room'] = '101'
    assert client.post('/retirada',data=second).status_code == 303


def test_history_filters_all_records_before_pagination(client):
    from test_app import login
    # >300 encerrados: pedidos antigos devem continuar acessíveis pela pesquisa.
    db = connect()
    for i in range(310):
        db.execute("INSERT INTO loans(professor_name,room,quantity,requested_at,start_at,expected_return_at,status) VALUES (?,?,?,?,?,?,'cancelled')",
                   (f'Professor {i:03}', '210' if i%2==0 else '101', 1, s.stamp(), s.stamp(), s.stamp()))
    db.close()
    login(client)
    page = client.get('/admin/historico?room=210&date=2026-10-13&status=cancelled').get_data(as_text=True)
    assert '155 pedido(s)' in page and page.count('class="panel history-item"') == 50
    assert 'room=210' in page and 'page=2' in page
    page = client.get('/admin/historico?room=210&page=4').get_data(as_text=True)
    assert page.count('class="panel history-item"') == 5
    assert 'Professor 000' in client.get('/admin/historico?search=Professor%20000').get_data(as_text=True)
    assert '0 pedido(s)' in client.get('/admin/historico?date=2026-10-12').get_data(as_text=True)
    assert '0 pedido(s)' in client.get('/admin/historico?search=%27%20OR%201%3D1--').get_data(as_text=True)
    assert client.get('/admin/historico?page=abc&date=bad&status=bad').status_code == 200
