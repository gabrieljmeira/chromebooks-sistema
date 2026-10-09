import secrets
from datetime import timedelta

import pytest
from werkzeug.security import generate_password_hash

from services import get_history, now, stock_count


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
    for action in ('confirmar', 'devolver', 'cancelar'):
        assert client.post(f'/admin/{action}/1').location.endswith('/admin/login')
    response = client.post('/retirada', data={
        'csrf': csrf(client), 'name': 'Prof. Ana', 'room': '203', 'quantity': '4',
        'expected_return': (now() + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M'),
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'#1' in response.data
    assert b'Prof. Ana' not in response.data
    assert stock_count() == 20
    response = client.post('/admin/login', data={
        'csrf': csrf(client), 'password': 'senha-errada',
    })
    assert b'Senha incorreta' in response.data
    response = client.post('/admin/login', data={
        'csrf': csrf(client), 'password': 'senha-apenas-para-teste',
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'Prof. Ana' in response.data
    response = client.post('/admin/confirmar/1', data={'csrf': csrf(client)}, follow_redirects=True)
    assert response.status_code == 200
    assert b'CH-001, CH-002, CH-003, CH-004' in response.data
    assert stock_count() == 16
    assert client.post('/admin/devolver/1', data={'csrf': csrf(client)}, follow_redirects=True).status_code == 200
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
