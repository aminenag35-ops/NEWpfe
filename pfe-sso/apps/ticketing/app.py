"""
Application Ticketing / Helpdesk
"""

import os
import sys
import datetime

sys.path.insert(0, "/app/shared")

from flask import Flask, render_template, request as flask_request, redirect, url_for, flash
from oidc import init_oidc, login_redirect, handle_callback, logout, login_required, require_role, get_current_user
from database import query, execute

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("APP_SECRET_KEY", "dev")
app.config["APP_NAME"] = "Ticketing"

init_oidc(app)


@app.context_processor
def inject_server_ip():
    return {"server_ip": os.environ.get("SERVER_IP", "localhost")}


def ensure_user(user):
    existing = query("SELECT id FROM users WHERE keycloak_id = %s", (user["sub"],))
    if not existing:
        execute("INSERT INTO users (keycloak_id, username, email) VALUES (%s, %s, %s)",
                (user["sub"], user["username"], user["email"]))


@app.route("/login")
def login():
    return login_redirect()

@app.route("/callback")
def callback():
    result = handle_callback()
    user = get_current_user()
    if user:
        ensure_user(user)
    return result

@app.route("/logout")
def do_logout():
    return logout()


@app.route("/")
@login_required
def index():
    user = get_current_user()
    ensure_user(user)
    if "admin" in user.get("roles", []) or "manager" in user.get("roles", []):
        tickets = query("SELECT * FROM tickets ORDER BY created_at DESC")
    else:
        tickets = query("SELECT * FROM tickets WHERE created_by = %s ORDER BY created_at DESC", (user["sub"],))
    stats = {"open": len([t for t in tickets if t["status"] == "open"]),
             "in_progress": len([t for t in tickets if t["status"] == "in_progress"]),
             "closed": len([t for t in tickets if t["status"] == "closed"])}
    return render_template("index.html", app_name="Ticketing", user=user, tickets=tickets, stats=stats)


@app.route("/ticket/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    user = get_current_user()
    if flask_request.method == "POST":
        title = flask_request.form.get("title", "").strip()
        description = flask_request.form.get("description", "").strip()
        priority = flask_request.form.get("priority", "medium")
        if not title:
            flash("Le titre est obligatoire.", "danger")
            return render_template("new_ticket.html", app_name="Ticketing", user=user)
        execute("INSERT INTO tickets (title, description, priority, status, created_by, created_by_name) VALUES (%s, %s, %s, 'open', %s, %s)",
                (title, description, priority, user["sub"], user["username"]))
        ticket = query("SELECT id FROM tickets ORDER BY id DESC LIMIT 1")[0]
        execute("INSERT INTO ticket_history (ticket_id, status, changed_by, changed_at) VALUES (%s, 'open', %s, %s)",
                (ticket["id"], user["username"], datetime.datetime.utcnow()))
        flash("Ticket créé avec succès !", "success")
        return redirect("/")
    return render_template("new_ticket.html", app_name="Ticketing", user=user)


@app.route("/ticket/<int:ticket_id>")
@login_required
def view_ticket(ticket_id):
    user = get_current_user()
    tickets = query("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
    if not tickets:
        flash("Ticket introuvable.", "danger")
        return redirect("/")
    ticket = tickets[0]
    if ticket["created_by"] != user["sub"] and "admin" not in user.get("roles", []) and "manager" not in user.get("roles", []):
        flash("Accès refusé.", "danger")
        return redirect("/")
    history = query("SELECT * FROM ticket_history WHERE ticket_id = %s ORDER BY changed_at DESC", (ticket_id,))
    return render_template("view_ticket.html", app_name="Ticketing", user=user, ticket=ticket, history=history)


@app.route("/ticket/<int:ticket_id>/status", methods=["POST"])
@require_role("admin", "manager")
def change_status(ticket_id):
    user = get_current_user()
    new_status = flask_request.form.get("status")
    if new_status not in ("open", "in_progress", "closed"):
        flash("Statut invalide.", "danger")
        return redirect(f"/ticket/{ticket_id}")
    execute("UPDATE tickets SET status = %s WHERE id = %s", (new_status, ticket_id))
    execute("INSERT INTO ticket_history (ticket_id, status, changed_by, changed_at) VALUES (%s, %s, %s, %s)",
            (ticket_id, new_status, user["username"], datetime.datetime.utcnow()))
    flash(f"Statut changé en « {new_status} ».", "success")
    return redirect(f"/ticket/{ticket_id}")


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
