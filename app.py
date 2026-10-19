"""Flask sem frameworks adicionais; sessão curta, CSRF e ações idempotentes."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import date, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash
import services
from rooms import ROOMS

load_dotenv()
app = Flask(__name__)
secret = os.getenv("SECRET_KEY", "")
if len(secret) < 32 or secret.startswith("COLOQUE_AQUI"):
    raise RuntimeError("Defina SECRET_KEY aleatória com pelo menos 32 caracteres.")
app.config.update(
    SECRET_KEY=secret,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.getenv("VERCEL"))
    or os.getenv("COOKIE_SECURE") == "1",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=False,
    MAX_CONTENT_LENGTH=16 * 1024,
)
signer = URLSafeTimedSerializer(secret, salt="form-operations-v1")


def password_hash():
    return os.getenv("ADMIN_PASSWORD_HASH", "").strip()


def auth_version():
    return hashlib.sha256(password_hash().encode()).hexdigest()


def authorized():
    return bool(
        session.get("admin")
        and 0 <= time.time() - session.get("authenticated_at", 0) < 8 * 3600
        and hmac.compare_digest(session.get("auth_version", ""), auth_version())
    )


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def form_token(scope):
    return signer.dumps(
        {"scope": scope, "nonce": secrets.token_urlsafe(32), "session": csrf_token()}
    )


def operation(scope):
    try:
        data = signer.loads(request.form.get("operation", ""), max_age=8 * 3600)
    except (BadSignature, SignatureExpired):
        abort(400, description="Formulário expirado. Atualize a página.")
    if data.get("scope") != scope or data.get("session") != session.get("csrf"):
        abort(400, description="Formulário inválido. Atualize a página.")
    return data["nonce"]


app.jinja_env.globals.update(csrf_token=csrf_token, form_token=form_token, rooms=ROOMS)


@app.before_request
def protect_post():
    if request.method == "POST":
        expected = session.get("csrf", "")
        submitted = request.form.get("csrf", "")
        if not expected or not hmac.compare_digest(
            expected.encode(), submitted.encode()
        ):
            abort(
                400,
                description="Formulário expirado. Atualize a página e tente novamente.",
            )


@app.after_request
def headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    response.headers["Cache-Control"] = "no-store, private"
    if app.config["SESSION_COOKIE_SECURE"]:
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response


def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not authorized():
            if request.path == "/admin/estado":
                return jsonify(error="Entre novamente no painel."), 401
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)

    return wrapped


def limit(scope, count):
    # Não confia em X-Forwarded-For fornecido pelo cliente. Guarda só HMAC temporário.
    identity = hmac.new(
        secret.encode(), (request.remote_addr or "unknown").encode(), hashlib.sha256
    ).hexdigest()
    if not services.rate_limit(scope + ":" + identity, count, 600):
        abort(
            429,
            description="Muitas tentativas. Aguarde alguns minutos e tente novamente.",
        )


@app.route("/", methods=["GET", "POST"])
@app.route("/retirada", methods=["GET", "POST"])
def retirada():
    status = 200
    if request.method == "POST":
        token = operation("request")
        limit("requests", 30)
        if request.form.get("website"):
            return render_template("success.html", request_id=None)
        try:
            loan_id = services.request_loan(
                request.form.get("name"),
                request.form.get("room"),
                request.form.get("quantity"),
                request.form.get("expected_return"),
                request.form.get("kind"),
                request.form.get("start_time"),
                token,
            )
            return redirect(url_for("success", request_id=loan_id), 303)
        except services.ValidationError as exc:
            flash(str(exc), "error")
            status = 422
    return render_template("request.html"), status


@app.get("/salas/disponibilidade")
def room_availability():
    # Consulta pública retorna apenas salas ocupadas, sem nomes ou códigos de pedidos.
    try:
        return jsonify(services.room_availability(
            request.args.get("kind", "now"), request.args.get("start_time"),
            request.args.get("expected_return"),
        ))
    except services.ValidationError as exc:
        return jsonify(error=str(exc)), 422


@app.get("/enviado/<int:request_id>")
def success(request_id):
    return render_template("success.html", request_id=request_id)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    status = 200
    if request.method == "POST":
        limit("login", 10)
        valid = False
        try:
            stored = password_hash()
            if (
                stored.startswith(("scrypt:", "pbkdf2:"))
                and len(request.form.get("password", "")) <= 1024
            ):
                valid = check_password_hash(stored, request.form.get("password", ""))
        except (ValueError, TypeError):
            pass
        if valid:
            session.clear()
            session.permanent = True
            session["admin"] = True
            session["authenticated_at"] = time.time()
            session["auth_version"] = auth_version()
            return redirect(url_for("admin_dashboard"), 303)
        flash(
            "Não foi possível entrar. Confira a senha e a configuração administrativa.",
            "error",
        )
        status = 401
    return render_template("login.html"), status


@app.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"), 303)


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("dashboard.html", data=services.get_dashboard())


@app.get("/admin/estado")
@admin_required
def admin_state():
    data = services.get_dashboard()
    alerts = [
        {
            "id": l["id"],
            "expected": l["expected_return_at"],
            "remaining": l["remaining"],
        }
        for l in data["active"]
        if l["remaining"] > 0 and not l["needs_review"]
    ]
    return jsonify(
        html=render_template("_dashboard.html", data=data),
        loans=alerts,
        server_time=data["server_time"],
        pending=[{"id": loan["id"]} for loan in data["pending"]],
    )


@app.get("/admin/historico")
@admin_required
def admin_history():
    filters = {key: request.args.get(key, "").strip() for key in ("search", "room", "date", "status")}
    filters["search"] = filters["search"][:100]
    filters["room"] = filters["room"][:40]  # Permite consultar também salas antigas.
    if filters["status"] not in ("", "pending", "active", "returned", "cancelled", "overdue", "review"):
        filters["status"] = ""
    if filters["date"]:
        try:
            filters["date"] = date.fromisoformat(filters["date"]).isoformat()
        except ValueError:
            filters["date"] = ""
    try:
        filters["page"] = max(1, min(int(request.args.get("page", "1")), 1000000))
    except ValueError:
        filters["page"] = 1
    data = services.get_history(filters)
    link_args = {key: value for key, value in filters.items() if key != "page" and value}
    return render_template("history.html", data=data, filters=filters,
                           previous_url=url_for("admin_history", **link_args, page=data["page"] - 1),
                           next_url=url_for("admin_history", **link_args, page=data["page"] + 1))


@app.post("/admin/<action>/<int:loan_id>")
@admin_required
def admin_action(action, loan_id):
    if action not in ("entregar", "devolver", "cancelar", "conferir"):
        abort(404)
    token = operation(f"{action}:{loan_id}")
    try:
        if action == "entregar":
            services.deliver_loan(loan_id, request.form.getlist("devices"), token)
        elif action == "devolver":
            services.return_loan(loan_id, request.form.getlist("devices"), token)
        elif action == "cancelar":
            services.cancel_loan(loan_id, token)
        else:
            services.reconcile_loan(
                loan_id,
                request.form.getlist("devices"),
                request.form.get("reason"),
                token,
            )
        flash("Registro salvo.", "success")
    except services.ValidationError as exc:
        flash(str(exc), "error")
    return redirect(
        url_for("admin_history" if action == "conferir" else "admin_dashboard"), 303
    )


@app.errorhandler(400)
@app.errorhandler(413)
@app.errorhandler(429)
def input_error(error):
    return render_template("error.html", message=error.description), error.code


@app.errorhandler(sqlite3.OperationalError)
def sqlite_error(error):
    app.logger.error("Falha operacional no banco local: %s", type(error).__name__)
    return (
        render_template(
            "error.html",
            message="Banco indisponível. Tente novamente ou confira a inicialização.",
        ),
        503,
    )


@app.errorhandler(500)
def server_error(error):
    return (
        render_template(
            "error.html",
            message="Não foi possível concluir. Contate a TI; não repita a operação sem conferir o painel.",
        ),
        500,
    )


if __name__ == "__main__":
    app.run(debug=False)
