"""Flask sem frameworks adicionais; sessão curta, CSRF e ações idempotentes."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import csv
import io
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
    g,
    Response,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash
import services
import management
import accounts
from database import DatabaseUnavailable, connect, one, rows
from rooms import ROOMS, room_name

load_dotenv()
app = Flask(__name__)
app.jinja_env.filters["room_name"] = room_name
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
    basic = bool(
        session.get("admin")
        and 0 <= time.time() - session.get("authenticated_at", 0) < 8 * 3600
    )
    if not basic:
        return False
    if session.get("user_id"):
        if not hasattr(g, "identity"):
            g.identity = accounts.get_user(session["user_id"])
        user = g.identity
        if not user or not user["active"] or not hmac.compare_digest(session.get("user_version", ""), user["version"]):
            return False
        g.role = user["role"]
        return True
    if not hasattr(g, "accounts_configured"):
        g.accounts_configured = accounts.configured()
    g.role = "manager"
    return not g.accounts_configured and hmac.compare_digest(session.get("auth_version", ""), auth_version())


def is_manager():
    return getattr(g, "role", "") == "manager"


@app.template_filter("field_label")
def field_label(value):
    return {"professor_name": "Professor", "room": "Sala", "quantity": "Quantidade", "start_at": "Início solicitado", "expected_return_at": "Devolução prevista", "kind": "Tipo de pedido", "device_id": "Aparelho", "returned_at": "Recebimento"}.get(value, value)


@app.template_filter("change_value")
def change_value(value, field):
    if value is None:
        return "Sem registro / em uso"
    if field == "device_id":
        return f"CH-{int(value):03}"
    if field.endswith("_at"):
        return services.datetime_label(value)
    if field == "kind":
        return "Agendado" if value == "scheduled" else "Pedir agora"
    return value


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


app.jinja_env.globals.update(csrf_token=csrf_token, form_token=form_token, rooms=ROOMS, is_manager=is_manager)


@app.context_processor
def scheduling_dates():
    from datetime import timedelta
    today = services.now().date()
    return {"schedule_today": today.isoformat(), "schedule_last": (today + timedelta(days=2)).isoformat()}


@app.post("/retirada/revisar")
def review_request():
    limit("reviews", 60)
    operation("request")
    if request.form.get("website"):
        return render_template("success.html", request_id=None)
    if request.form.get("edit"):
        return render_template("request.html")
    try:
        name = request.form.get("name", "").strip()
        room = request.form.get("room", "")
        amount = services.quantity(request.form.get("quantity"))
        if not 3 <= len(name) <= 100 or room not in ROOMS:
            raise services.ValidationError("Confira o nome do professor e a sala.")
        availability = services.room_availability(request.form.get("kind"), request.form.get("start_time"), request.form.get("expected_return"), request.form.get("use_date"))
        if room in availability["busy"] or amount > availability["available"]:
            raise services.ValidationError("Sala ou quantidade indisponível neste período. Confira o pedido.")
        return render_template("review_request.html", availability=availability)
    except services.ValidationError as exc:
        flash(str(exc), "error")
        return render_template("request.html"), 422


@app.before_request
def protect_post():
    g.actor_token = services.actor.set(session.get("username", "TI (senha compartilhada)") if session.get("admin") else "Professor (formulário)")
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


@app.teardown_request
def reset_actor(error):
    if hasattr(g, "actor_token"):
        services.actor.reset(g.actor_token)
        del g.actor_token


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


def manager_required(fn):
    @admin_required
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not is_manager():
            abort(403, description="Este recurso exige uma conta de gestor da TI.")
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
                use_date=request.form.get("use_date"),
            )
            return redirect(url_for("success", request_id=loan_id), 303)
        except services.ValidationError as exc:
            flash(str(exc), "error")
            status = 422
    return render_template("request.html"), status


@app.get("/salas/disponibilidade")
def room_availability():
    # Consulta pública retorna salas ocupadas e capacidade, sem dados dos professores.
    try:
        return jsonify(services.room_availability(
            request.args.get("kind", "now"), request.args.get("start_time"),
            request.args.get("expected_return"), request.args.get("use_date"),
        ))
    except services.ValidationError as exc:
        return jsonify(error=str(exc)), 422


@app.get("/enviado/<int:request_id>")
def success(request_id):
    return render_template("success.html", request_id=request_id)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    status = 200
    individual = accounts.configured()
    if request.method == "POST":
        limit("login", 10)
        valid = False
        user = None
        try:
            stored = password_hash()
            if individual and len(request.form.get("password", "")) <= 1024:
                user = accounts.authenticate(request.form.get("username", ""), request.form.get("password", ""))
                valid = user is not None
            elif not individual and (
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
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["user_version"] = user["version"]
            return redirect(url_for("admin_dashboard"), 303)
        flash(
            "Não foi possível entrar. Confira a senha e a configuração administrativa.",
            "error",
        )
        status = 401
    return render_template("login.html", individual=individual), status


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
        pending=[{"id": loan["id"], "scheduled": loan["scheduled_later"], "start": loan["start_at_label"]} for loan in data["pending"]],
        deliveries=[{"id": loan["id"], "start": loan["start_at"], "expected": loan["expected_return_at"]} for loan in data["pending"] if loan["kind"] == "scheduled" and not loan["expired"]],
    )


@app.get("/admin/historico")
@admin_required
def admin_history():
    filters = history_filters()
    data = services.get_history(filters)
    link_args = {key: value for key, value in filters.items() if key != "page" and value}
    return render_template("history.html", data=data, filters=filters,
                           export_url=url_for("admin_export", **link_args),
                           previous_url=url_for("admin_history", **link_args, page=data["page"] - 1),
                           next_url=url_for("admin_history", **link_args, page=data["page"] + 1))


def history_filters():
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
    return filters


@app.get("/admin/exportar.csv")
@admin_required
def admin_export():
    where, params = services.history_selection(history_filters())
    db = connect()
    try:
        db.execute("BEGIN")
        loans = rows(db.execute("SELECT * FROM loans" + where + " ORDER BY id DESC", params))
        allocations = rows(db.execute("SELECT a.*,d.code FROM allocations a JOIN devices d ON d.id=a.device_id ORDER BY a.id"))
        db.commit()
    finally:
        db.close()
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Pedido", "Professor", "Sala", "Quantidade", "Situação", "Início solicitado", "Entrega real", "Previsão devolução", "Devolução completa", "Aparelhos", "Ainda em uso"])
    def safe(value):
        value = str(value if value is not None else "")
        return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")) else value
    for loan in loans:
        devices = [a for a in allocations if a["loan_id"] == loan["id"]]
        row = [loan["id"], loan["professor_name"], loan["room"], loan["quantity"], loan["status"], *[services.datetime_label(loan[key]) for key in ("start_at", "confirmed_at", "expected_return_at", "returned_at")], ", ".join(a["code"] for a in devices), ", ".join(a["code"] for a in devices if a["returned_at"] is None)]
        writer.writerow([safe(value) for value in row])
    return Response("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="historico-chromebooks.csv"'})


@app.route("/admin/inventario", methods=["GET", "POST"])
@admin_required
def admin_inventory():
    if request.method == "POST":
        token = operation("maintenance")
        try:
            state = request.form.get("state")
            if state not in ("unavailable", "available"):
                raise services.ValidationError("Selecione a situação do aparelho.")
            management.set_unavailable(request.form.get("code"), state == "unavailable", request.form.get("reason"), token)
            flash("Situação do aparelho registrada. Confira também as reservas no painel.", "success")
        except services.ValidationError as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin_inventory"), 303)
    devices, events = management.inventory()
    return render_template("inventory.html", devices=devices, events=events)


@app.route("/admin/pedido/<int:loan_id>/<action>", methods=["GET", "POST"])
@admin_required
def admin_manage_loan(loan_id, action):
    if action not in ("editar", "prorrogar", "corrigir"):
        abort(404)
    loan, allocations = management.correction_data(loan_id)
    status = 200
    if request.method == "POST":
        token = operation(f"{action}:{loan_id}")
        try:
            if action == "editar":
                management.edit_pending(loan_id, request.form.get("name"), request.form.get("room"), request.form.get("quantity"), request.form.get("start_time"), request.form.get("expected_return"), request.form.get("reason"), token, use_date=request.form.get("use_date"))
            elif action == "prorrogar":
                management.extend_loan(loan_id, request.form.get("expected_return"), request.form.get("reason"), token)
            else:
                management.correct_allocation(loan_id, request.form.get("allocation_id"), request.form.get("code"), request.form.get("state"), request.form.get("reason"), token)
            flash("Alteração registrada no histórico.", "success")
            return redirect(url_for("admin_dashboard"), 303)
        except services.ValidationError as exc:
            flash(str(exc), "error")
            status = 422
    return render_template("manage_loan.html", loan=loan, allocations=allocations, action=action), status


@app.route("/admin/contas", methods=["GET", "POST"])
@manager_required
def admin_accounts():
    abort(404)


@app.route("/admin/minha-senha", methods=["GET", "POST"])
@admin_required
def admin_password():
    if not session.get("user_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        token = operation("password")
        try:
            accounts.change_password(session["user_id"], request.form.get("old_password"), request.form.get("password"), token)
            session.clear()
            flash("Senha alterada. Entre novamente.", "success")
            return redirect(url_for("admin_login"), 303)
        except services.ValidationError as exc:
            flash(str(exc), "error")
    return render_template("password.html")


@app.get("/saude")
def health():
    try:
        db = connect()
        try:
            db.execute("SELECT id FROM devices LIMIT 1")
            db.execute("SELECT start_at FROM loans LIMIT 1")
            db.execute("SELECT id FROM allocations LIMIT 1")
        finally:
            db.close()
        return jsonify(status="ok")
    except DatabaseUnavailable:
        return jsonify(status="indisponivel"), 503


@app.get("/admin/diagnostico")
@manager_required
def admin_diagnostics():
    abort(404)


@app.post("/admin/backup")
@manager_required
def admin_backup():
    abort(404)


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
@app.errorhandler(403)
@app.errorhandler(413)
@app.errorhandler(429)
def input_error(error):
    return render_template("error.html", message=error.description), error.code


@app.errorhandler(DatabaseUnavailable)
def database_unavailable(error):
    app.logger.error("Banco indisponível: %s", type(error.__cause__).__name__ if error.__cause__ else "configuracao")
    if request.path == "/admin/estado" or request.path == "/salas/disponibilidade":
        return jsonify(error=str(error)), 503
    return render_template("error.html", message=str(error) + " Se você estava salvando uma alteração, confira o painel antes de repetir."), 503


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
