"""
Application IAM – Gestion des accès
"""

import os
import sys
import datetime

sys.path.insert(0, "/app/shared")

from flask import Flask, render_template, redirect, flash
from oidc import init_oidc, login_redirect, handle_callback, logout, login_required, require_role, get_current_user
from database import query, execute

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev")
app.config["APP_NAME"] = "IAM"

init_oidc(app)


@app.context_processor
def inject_server_ip():
    return {"server_ip": os.environ.get("SERVER_IP", "localhost")}


def log_action(user, action):
    execute(
        "INSERT INTO audit_log (keycloak_id, username, action, timestamp) VALUES (%s, %s, %s, %s)",
        (user["sub"], user["username"], action, datetime.datetime.utcnow()),
    )


@app.route("/login")
def login():
    return login_redirect()


@app.route("/callback")
def callback():
    result = handle_callback()
    user = get_current_user()
    if user:
        existing = query("SELECT id FROM users WHERE keycloak_id = %s", (user["sub"],))
        if not existing:
            execute(
                "INSERT INTO users (keycloak_id, username, email) VALUES (%s, %s, %s)",
                (user["sub"], user["username"], user["email"]),
            )
        log_action(user, "LOGIN")
    return result


@app.route("/logout")
def do_logout():
    user = get_current_user()
    if user:
        log_action(user, "LOGOUT")
    return logout()


@app.route("/")
@login_required
def index():
    user = get_current_user()
    log_action(user, "VIEW_DASHBOARD")
    users_count = query("SELECT COUNT(*) as cnt FROM users")[0]["cnt"]
    logs_count = query("SELECT COUNT(*) as cnt FROM audit_log")[0]["cnt"]
    return render_template(
        "index.html",
        app_name="IAM",
        user=user,
        users_count=users_count,
        logs_count=logs_count,
    )


@app.route("/users")
@require_role("admin", "manager")
def users_list():
    user = get_current_user()
    log_action(user, "VIEW_USERS_LIST")
    users = query("SELECT * FROM users ORDER BY created_at DESC")
    return render_template("users.html", app_name="IAM", user=user, users=users)


@app.route("/audit")
@require_role("admin")
def audit_log():
    user = get_current_user()
    log_action(user, "VIEW_AUDIT_LOG")
    logs = query("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 100")
    return render_template("audit.html", app_name="IAM", user=user, logs=logs)


@app.route("/profile")
@login_required
def profile():
    user = get_current_user()
    log_action(user, "VIEW_PROFILE")
    return render_template("profile.html", app_name="IAM", user=user)


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)
