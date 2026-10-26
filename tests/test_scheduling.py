from datetime import timedelta
import secrets
import pytest
import services as s
from test_app import public_data, fields, login


@pytest.mark.parametrize('days', [0, 1, 2])
def test_schedule_allowed_days(days):
    day = (s.now().date() + timedelta(days=days)).isoformat()
    start = '11:00' if days == 0 else '08:00'
    identifier = s.request_loan('Professora Ana', '101', 5, '12:00', 'scheduled', start, secrets.token_urlsafe(32), use_date=day)
    loan = s.get_dashboard()['pending'][0]
    assert loan['id'] == identifier
    assert loan['start_at'].startswith(day)
    assert loan['expected_return_at'].startswith(day)
    assert s.stock_count() == 20


@pytest.mark.parametrize('day', ['2026-10-12', '2026-10-16', 'invalid', '2026-02-30'])
def test_reject_invalid_or_outside_date(day):
    with pytest.raises(s.ValidationError):
        s.room_availability('scheduled', '08:00', '09:00', day)


def test_same_room_other_day_and_boundary():
    s.request_loan('Professora Ana', '101', 15, '09:00', 'scheduled', '08:00', secrets.token_urlsafe(32), use_date='2026-10-14')
    assert s.room_availability('scheduled', '08:00', '09:00', '2026-10-14')['available'] == 5
    assert '101' in s.room_availability('scheduled', '08:00', '09:00', '2026-10-14')['busy']
    assert s.room_availability('scheduled', '09:00', '10:00', '2026-10-14')['available'] == 20
    assert s.room_availability('scheduled', '08:00', '09:00', '2026-10-15')['busy'] == []


def test_review_edit_confirmation_without_js(client):
    data = public_data(client, kind='scheduled', start_time='08:00', expected_return='09:00', use_date='2026-10-15')
    review = client.post('/retirada/revisar', data=data)
    assert review.status_code == 200
    assert b'15/10/2026' in review.data
    assert s.get_dashboard()['pending'] == []
    confirmed = fields(review, '/retirada')
    edited = client.post('/retirada/revisar', data={**confirmed, 'edit': '1'})
    assert b'value="2026-10-15"' in edited.data
    assert client.post('/retirada', data=confirmed).status_code == 303
    assert client.post('/retirada', data=confirmed).status_code == 303
    assert len(s.get_dashboard()['pending']) == 1


def test_review_revalidates_at_confirmation(client):
    data = public_data(client, kind='scheduled', start_time='08:00', expected_return='09:00', use_date='2026-10-15')
    review = client.post('/retirada/revisar', data=data)
    s.request_loan('Outro professor', '203', 20, '09:00', 'scheduled', '08:00', secrets.token_urlsafe(32), use_date='2026-10-15')
    assert client.post('/retirada', data=fields(review, '/retirada')).status_code == 422
    assert len(s.get_dashboard()['pending']) == 1


def test_admin_can_edit_future_day(client):
    import management
    identifier = s.request_loan('Professora Ana', '101', 5, '09:00', 'scheduled', '08:00', secrets.token_urlsafe(32), use_date='2026-10-14')
    management.edit_pending(identifier, 'Professora Ana', '103', 6, '09:00', '10:00', 'Reagendamento solicitado pela professora', secrets.token_urlsafe(32), use_date='2026-10-15')
    loan = s.get_dashboard()['pending'][0]
    assert loan['start_at'].startswith('2026-10-15T09:00')
    login(client)
    assert b'15/10/2026' in client.get('/admin').data
