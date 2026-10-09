import secrets

import pytest
from werkzeug.security import generate_password_hash

from services import get_history, stock_count


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv('SECRET_KEY', secrets.token_urlsafe(48))
    monkeypatch.setenv('ADMIN_PASSWORD_HASH', generate_password_hash('senha-apenas-para-teste'))
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('COOKIE_SECURE', raising=False)
    from app import app
    monkeypatch.setitem(app.config, 'TESTING', True)
    return app.test_client()


def csrf(client):
    with client.session_transaction() as session:
        return session['csrf']


def test_local_http_lifecycle(client):
    for path in ('/', '/retirada', '/admin/login', '/static/styles.css'):
        assert client.get(path).status_code == 200
    for path in ('/admin', '/admin/historico'):
        assert client.get(path).location.endswith('/admin/login')
    assert client.post('/admin/devolver/1').location.endswith('/admin/login')
    assert client.post('/admin/confirmar/1').status_code == 404
    assert client.post('/admin/cancelar/1').status_code == 404
    response = client.post('/retirada', data={
        'csrf': csrf(client), 'name': 'Prof. Ana', 'room': '203', 'quantity': '4',
        'expected_return': '15:00',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'#1' in response.data
    assert b'Prof. Ana' not in response.data
    assert stock_count() == 16
    assert get_history()[0]['status'] == 'active'
    response = client.post('/admin/login', data={
        'csrf': csrf(client), 'password': 'senha-errada',
    })
    assert b'Senha incorreta' in response.data
    response = client.post('/admin/login', data={
        'csrf': csrf(client), 'password': 'senha-apenas-para-teste',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Prof. Ana' in response.data
    assert b'Confirmar entrega' not in response.data
    assert b'Quantidade devolvida' in response.data
    assert b'CH-001, CH-002, CH-003, CH-004' in response.data
    assert stock_count() == 16
    assert client.post('/admin/devolver/1', data={'quantity': '1'}).status_code == 400
    assert stock_count() == 16
    assert client.post('/admin/devolver/1', data={'csrf': csrf(client), 'quantity': '3'}, follow_redirects=True).status_code == 200
    assert stock_count() == 19
    assert get_history()[0]['remaining_quantity'] == 1
    response = client.post('/admin/devolver/1', data={'csrf': csrf(client), 'quantity': '2'}, follow_redirects=True)
    assert 'não pode superar' in response.get_data(as_text=True)
    assert stock_count() == 19
    assert client.post('/admin/devolver/1', data={'csrf': csrf(client), 'quantity': '1'}, follow_redirects=True).status_code == 200
    assert stock_count() == 20
    assert b'Devolvido' in client.get('/admin/historico').data
    assert get_history()[0]['status'] == 'returned'
    assert client.post('/admin/logout', data={'csrf': csrf(client)}).status_code == 302
    assert client.get('/admin').location.endswith('/admin/login')


@pytest.mark.parametrize('token', ['', 'incorreto', 'inválido'])
def test_invalid_csrf_is_rejected_without_server_error(client, token):
    client.get('/retirada')
    assert client.post('/retirada', data={'csrf': token}).status_code == 400
    assert get_history() == []


def test_stale_form_cannot_take_more_than_available(client):
    from services import request_loan
    page = client.get('/retirada')
    assert b'inputmode="numeric"' in page.data
    assert b'datetime-local' not in page.data
    request_loan('Prof. Bruno', '204', '18', '15:00')
    response = client.post('/retirada', data={
        'csrf': csrf(client), 'name': 'Prof. Ana', 'room': '203',
        'quantity': '4', 'expected_return': '15:00',
    })
    assert 'Não há essa quantidade disponível' in response.get_data(as_text=True)
    assert stock_count() == 2
    assert len(get_history()) == 1


def test_honeypot_does_not_change_inventory(client):
    client.get('/retirada')
    response = client.post('/retirada', data={
        'csrf': csrf(client), 'website': 'spam', 'name': 'Robô',
        'room': '203', 'quantity': '20', 'expected_return': '15:00',
    })
    assert response.status_code == 200
    assert stock_count() == 20
    assert get_history() == []
