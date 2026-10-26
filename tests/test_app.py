from html.parser import HTMLParser
import secrets
import pytest
import services as s


class Forms(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.current = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.current = {"action": attrs.get("action", ""), "fields": {}}
            self.forms.append(self.current)
        if (
            tag == "input"
            and self.current is not None
            and attrs.get("type") == "hidden"
        ):
            self.current["fields"][attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.current = None


def fields(response, action=""):
    return next(
        f["fields"]
        for f in Forms(response.get_data(as_text=True)).forms
        if f["action"] == action
    )


def login(client):
    data = fields(client.get("/admin/login"))
    data["password"] = "senha-exclusiva-teste"
    assert client.post("/admin/login", data=data).status_code == 303
    return client.get("/admin")


def public_data(client, **changes):
    data = fields(client.get("/retirada"), "/retirada/revisar")
    data.update(
        name="Prof. Ana", room="203", quantity="2", kind="now", expected_return="15:00"
    )
    data.update(changes)
    return data


def test_full_http_flow(client):
    data = public_data(client)
    assert client.post("/retirada", data=data).status_code == 303
    assert client.post("/retirada", data=data).status_code == 303
    assert len(s.get_history()["loans"]) == 1
    assert s.stock_count() == 20
    page = login(client)
    assert "Aguardando entrega pela TI" in page.get_data(as_text=True)
    action = "/admin/entregar/1"
    data = fields(page, action)
    data["devices"] = ["CH-004", "CH-015"]
    assert client.post(action, data=data).status_code == 303
    assert client.post(action, data=data).status_code == 303
    assert s.stock_count() == 18
    page = client.get("/admin")
    action = "/admin/devolver/1"
    data = fields(page, action)
    data["devices"] = ["CH-015"]
    client.post(action, data=data)
    client.post(action, data=data)
    assert s.stock_count() == 19
    page = client.get("/admin")
    data = fields(page, action)
    data["devices"] = ["CH-004"]
    client.post(action, data=data)
    assert s.stock_count() == 20
    assert b"Devolvido" in client.get("/admin/historico").data
    page = client.get("/admin")
    client.post("/admin/logout", data=fields(page, "/admin/logout"))
    assert client.get("/admin/estado").status_code == 401


def test_scheduled_request_and_cancel(client):
    data = public_data(
        client, kind="scheduled", start_time="1100", expected_return="1230"
    )
    assert client.post("/retirada", data=data).status_code == 303
    page = login(client)
    action = "/admin/cancelar/1"
    client.post(action, data=fields(page, action))
    assert s.get_history()["loans"][0]["status"] == "cancelled"


@pytest.mark.parametrize("path", ["/admin", "/admin/historico"])
def test_private_pages_require_login(client, path):
    response = client.get(path)
    assert response.status_code == 302 and response.location.endswith("/admin/login")


@pytest.mark.parametrize("action", ["entregar", "devolver", "cancelar", "conferir"])
def test_anonymous_cannot_mutate(client, action):
    data = public_data(client)
    client.post("/retirada", data=data)
    with client.session_transaction() as session:
        csrf = session["csrf"]
    response = client.post(f"/admin/{action}/1", data={"csrf": csrf})
    assert response.status_code == 302
    assert s.get_history()["loans"][0]["status"] == "pending"


@pytest.mark.parametrize("csrf", ["", "wrong", "inválido"])
def test_csrf_rejects_bad_tokens(client, csrf):
    data = public_data(client)
    data["csrf"] = csrf
    assert client.post("/retirada", data=data).status_code == 400
    assert s.get_history()["loans"] == []


def test_form_token_tamper_and_cross_session(client):
    data = public_data(client)
    data["operation"] += "x"
    assert client.post("/retirada", data=data).status_code == 400
    data = public_data(client)
    import app

    other = app.app.test_client()
    other_data = public_data(other)
    other_data["operation"] = data["operation"]
    assert other.post("/retirada", data=other_data).status_code == 400


def test_form_token_cannot_authorize_other_action(client):
    public = public_data(client)
    client.post("/retirada", data=public)
    page = login(client)
    data = fields(page, "/admin/entregar/1")
    data["devices"] = ["CH-001", "CH-002"]
    assert client.post("/admin/devolver/1", data=data).status_code == 400


def test_expired_token(client, monkeypatch):
    import itsdangerous.timed

    data = public_data(client)
    original = itsdangerous.timed.TimestampSigner.get_timestamp
    monkeypatch.setattr(
        itsdangerous.timed.TimestampSigner,
        "get_timestamp",
        lambda self: original(self) + 9 * 3600,
    )
    assert client.post("/retirada", data=data).status_code == 400


def test_login_bad_password_and_throttle(client):
    data = fields(client.get("/admin/login"))
    data["password"] = "errada"
    for _ in range(10):
        assert client.post("/admin/login", data=data).status_code == 401
    assert client.post("/admin/login", data=data).status_code == 429
    assert client.get("/admin/estado").status_code == 401


def test_malformed_password_configuration_is_not_500(client, monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "pbkdf2:garbage$salt$hash")
    data = fields(client.get("/admin/login"))
    data["password"] = "wrong"
    assert client.post("/admin/login", data=data).status_code == 401


def test_password_rotation_invalidates_session(client, monkeypatch):
    login(client)
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "changed")
    assert client.get("/admin/estado").status_code == 401


def test_signed_session_rejects_tampering(client):
    login(client)
    client.set_cookie("session", "forged-admin-session")
    assert client.get("/admin/estado").status_code == 401


def test_post_only_and_csrf_on_admin(client):
    login(client)
    assert client.get("/admin/devolver/1").status_code == 405
    assert (
        client.post("/admin/devolver/1", data={"devices": "CH-001"}).status_code == 400
    )


def test_html_escaping_and_public_privacy(client):
    data = public_data(client, name="<script>alert(1)</script>")
    client.post("/retirada", data=data)
    page = login(client)
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;" in page.data
    assert b"alert(1)" not in client.get("/enviado/1").data


def test_security_headers_and_cookie(client):
    response = client.get("/retirada")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "no-store" in response.headers["Cache-Control"]
    cookie = response.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie
    login(client)
    with client.session_transaction() as session:
        assert session.permanent


def test_secure_cookie_in_https_config(client):
    import app

    app.app.config["SESSION_COOKIE_SECURE"] = True
    response = client.get("/retirada")
    assert "Secure" in response.headers["Set-Cookie"]
    assert "Strict-Transport-Security" in response.headers


def test_honeypot_does_not_create_loan(client):
    data = public_data(client, website="bot")
    assert client.post("/retirada", data=data).status_code == 200
    assert s.get_history()["loans"] == []


def test_client_quantity_does_not_bypass_interval_validation(client):
    data = public_data(client, quantity="20")
    client.post("/retirada", data=data)
    data = public_data(client, quantity="1")
    assert client.post("/retirada", data=data).status_code == 422
    assert len(s.get_history()["loans"]) == 1


def test_api_only_delivered_outstanding_loans(client):
    a = s.request_loan("Prof. Ana", "101", 2, "15:00", token=secrets.token_urlsafe(32))
    login(client)
    assert client.get("/admin/estado").json["loans"] == []
    s.deliver_loan(a, ["CH-001", "CH-002"], secrets.token_urlsafe(32))
    data = client.get("/admin/estado").json
    assert len(data["loans"]) == 1 and data["loans"][0]["remaining"] == 2
    s.return_loan(a, ["CH-001", "CH-002"], secrets.token_urlsafe(32))
    assert client.get("/admin/estado").json["loans"] == []


def test_large_payload(client):
    assert client.post("/retirada", data={"name": "x" * 20000}).status_code == 413


def test_absolute_session_expiry_even_after_cookie_update(client):
    import time

    login(client)
    with client.session_transaction() as session:
        session["authenticated_at"] = time.time() - 8 * 3600 - 1
        session["another_change"] = "cookie updated after login"
    assert client.get("/admin/estado").status_code == 401
    assert client.get("/admin").location.endswith("/admin/login")


def test_polling_does_not_refresh_cookie(client):
    login(client)
    response = client.get("/admin/estado")
    assert response.status_code == 200
    assert "Set-Cookie" not in response.headers


def test_history_readable_movements_and_escaped_search(client):
    loan_id = s.request_loan('Ana " <script>', '203', 1, '15:00', token=secrets.token_urlsafe(32))
    s.deliver_loan(loan_id, ['CH-004'], secrets.token_urlsafe(32))
    login(client)
    page = client.get('/admin/historico').get_data(as_text=True)
    assert 'Entrega registrada' in page
    assert 'CH-004' in page
    assert '<script>' not in page
    assert 'id="history-search"' in page
    assert '<pre>' not in page
    assert s.get_history()['audit'][0]['detail']  # Original audit data preserved.


def test_pending_requests_in_dashboard_alert_feed(client):
    loan_id = s.request_loan('Ana', '203', 1, '15:00', token=secrets.token_urlsafe(32))
    login(client)
    data = client.get('/admin/estado').get_json()
    assert data['pending'] == [{'id': loan_id, 'scheduled': False, 'start': '13/10/2026 10:00'}]
    assert data['loans'] == []
    s.deliver_loan(loan_id, ['CH-004'], secrets.token_urlsafe(32))
    data = client.get('/admin/estado').get_json()
    assert data['pending'] == []
    assert data['loans'][0]['id'] == loan_id
