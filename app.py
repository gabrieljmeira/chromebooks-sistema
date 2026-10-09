"""Controle de empréstimos de Chromebooks — Flask + Vercel."""
from __future__ import annotations

import hmac
import os
import secrets
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from services import (
    ValidationError, get_dashboard, get_history,
    now, request_loan, return_loan, stock_count,
)

load_dotenv()

app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key or len(secret_key) < 32 or secret_key.startswith("COLOQUE_AQUI"):
    raise RuntimeError("Defina SECRET_KEY (mínimo 32 caracteres) no .env ou nas variáveis da Vercel.")
app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("VERCEL") == "1" or os.getenv("COOKIE_SECURE") == "1",
    MAX_CONTENT_LENGTH=10 * 1024,
)


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.path.startswith("/admin"):
        response.headers["Cache-Control"] = "no-store, private"
    return response


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


def check_csrf():
    expected = session.get("csrf", "")
    submitted = request.form.get("csrf", "")
    if not expected or not hmac.compare_digest(expected.encode("utf-8"), submitted.encode("utf-8")):
        abort(400, description="Formulário expirado. Atualize a página e tente novamente.")


def admin_required(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapped


@app.route("/", methods=["GET", "POST"])
@app.route("/retirada", methods=["GET", "POST"])
def retirada():
    if request.method == "POST":
        check_csrf()
        if request.form.get("website"):
            # Honeypot para bots; não registra dados.
            return render_template("success.html", request_id=None), 200
        try:
            request_id = request_loan(
                request.form.get("name"), request.form.get("room"),
                request.form.get("quantity"), request.form.get("expected_return"),
            )
        except ValidationError as exc:
            flash(str(exc), "error")
        else:
            return redirect(url_for("success", request_id=request_id))
    return render_template("request.html", available=stock_count(), current_time=now().strftime("%H:%M"))


@app.get("/enviado/<int:request_id>")
def success(request_id):
    # Só mostra ID enviado pela URL; não expõe nomes, sala ou outros dados.
    return render_template("success.html", request_id=request_id)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        check_csrf()
        password_hash = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
        if not password_hash or "$" not in password_hash:
            flash("Senha da TI ainda não configurada pelo administrador.", "error")
        elif check_password_hash(password_hash, request.form.get("password", "")):
            session.clear()
            session["admin"] = True
            flash("Acesso autorizado.", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Senha incorreta.", "error")
    return render_template("login.html")


@app.post("/admin/logout")
@admin_required
def admin_logout():
    check_csrf()
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_required
def admin_dashboard():
    return render_template("dashboard.html", data=get_dashboard())


@app.get("/admin/historico")
@admin_required
def admin_history():
    return render_template("history.html", loans=get_history())


@app.post("/admin/devolver/<int:loan_id>")
@admin_required
def admin_return(loan_id):
    check_csrf()
    try:
        return_loan(loan_id, request.form.get("quantity"))
        flash("Devolução registrada. Estoque atualizado.", "success")
    except ValidationError as exc:
        flash(str(exc), "error")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    # Apenas desenvolvimento local. Na Vercel a app é importada diretamente.
    app.run(debug=False)
