"""
Application Audit & Traçabilité
"""

import os
import sys
import datetime

sys.path.insert(0, "/app/shared")

from flask import Flask, render_template, request as flask_request, redirect
from oidc import init_oidc, login_redirect, handle_callback, logout, login_required, require_role, get_current_user
from database import query, execute

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev")
app.config["APP_NAME"] = "Audit"

init_oidc(app)


@app.context_processor
def inject_server_ip():
    return {"server_ip": os.environ.get("SERVER_IP", "localhost")}


def ensure_user(user):
    existing = query("SELECT id FROM users WHERE keycloak_id = %s", (user["sub"],))
    if not existing:
        execute("INSERT INTO users (keycloak_id, username, email) VALUES (%s, %s, %s)",
                (user["sub"], user["username"], user["email"]))


def log_action(user, action, details=""):
    execute("INSERT INTO action_logs (keycloak_id, username, action, details, timestamp) VALUES (%s, %s, %s, %s, %s)",
            (user["sub"], user["username"], action, details, datetime.datetime.utcnow()))


@app.route("/login")
def login():
    return login_redirect()

@app.route("/callback")
def callback():
    result = handle_callback()
    user = get_current_user()
    if user:
        ensure_user(user)
        log_action(user, "LOGIN", "Connexion à l'application Audit")
    return result

@app.route("/logout")
def do_logout():
    user = get_current_user()
    if user:
        log_action(user, "LOGOUT", "Déconnexion")
    return logout()


@app.route("/")
@login_required
def index():
    user = get_current_user()
    ensure_user(user)
    log_action(user, "VIEW_DASHBOARD", "")
    total_logs = query("SELECT COUNT(*) as cnt FROM action_logs")[0]["cnt"]
    total_users = query("SELECT COUNT(DISTINCT username) as cnt FROM action_logs")[0]["cnt"]
    today = datetime.date.today()
    today_logs = query("SELECT COUNT(*) as cnt FROM action_logs WHERE timestamp::date = %s", (today,))[0]["cnt"]
    recent = query("SELECT * FROM action_logs ORDER BY timestamp DESC LIMIT 10")
    return render_template("index.html", app_name="Audit", user=user, total_logs=total_logs, total_users=total_users, today_logs=today_logs, recent=recent)


@app.route("/logs")
@require_role("admin", "manager")
def logs_page():
    user = get_current_user()
    filter_user = flask_request.args.get("username", "").strip()
    filter_date_from = flask_request.args.get("date_from", "").strip()
    filter_date_to = flask_request.args.get("date_to", "").strip()
    filter_action = flask_request.args.get("action", "").strip()
    sql = "SELECT * FROM action_logs WHERE 1=1"
    params = []
    if filter_user:
        sql += " AND username ILIKE %s"; params.append(f"%{filter_user}%")
    if filter_date_from:
        sql += " AND timestamp >= %s"; params.append(filter_date_from)
    if filter_date_to:
        sql += " AND timestamp <= %s"; params.append(filter_date_to + " 23:59:59")
    if filter_action:
        sql += " AND action ILIKE %s"; params.append(f"%{filter_action}%")
    sql += " ORDER BY timestamp DESC LIMIT 200"
    logs = query(sql, params if params else None)
    all_users = query("SELECT DISTINCT username FROM action_logs ORDER BY username")
    all_actions = query("SELECT DISTINCT action FROM action_logs ORDER BY action")
    log_action(user, "VIEW_LOGS", f"Filtres: user={filter_user}, from={filter_date_from}, to={filter_date_to}")
    return render_template("logs.html", app_name="Audit", user=user, logs=logs, all_users=all_users, all_actions=all_actions,
                           filter_user=filter_user, filter_date_from=filter_date_from, filter_date_to=filter_date_to, filter_action=filter_action)


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5003))
    app.run(host="0.0.0.0", port=port, debug=True)
