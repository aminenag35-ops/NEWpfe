"""
APP 2 : Ticket + Profil utilisateur
====================================
- Login SSO
- Profil
- Création / liste / détail tickets
- Commentaires sur tickets
"""
import os
from flask import Flask, render_template, redirect, request, session, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor

import keycloak_lib as kc

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "dev")


def db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "postgres"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        dbname=os.getenv("DB_NAME", "ticketsdb"),
    )


# ========== Auth ==========
@app.route("/")
def index():
    if "user" not in session:
        return render_template("login.html")
    return redirect(url_for("tickets"))


@app.route("/login")
def login():
    return redirect(kc.login_url(url_for("callback", _external=True)))


@app.route("/callback")
def callback():
    code = request.args.get("code")
    tokens = kc.exchange_code(code, url_for("callback", _external=True))
    info = kc.userinfo(tokens["access_token"])
    info["roles"] = kc.parse_roles_from_token(tokens)
    session["user"] = info
    return redirect(url_for("tickets"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(kc.logout_url(url_for("index", _external=True)))


# ========== Profil ==========
@app.route("/profile")
@kc.login_required
def profile():
    return render_template("profile.html", user=session["user"], me=session["user"])


# ========== Tickets ==========
@app.route("/tickets")
@kc.login_required
def tickets():
    user = session["user"]
    conn = db()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Les admins/support voient tout, les users voient leurs tickets
        if "admin" in user["roles"] or "support" in user["roles"]:
            cur.execute("SELECT * FROM tickets ORDER BY created_at DESC")
        else:
            cur.execute("SELECT * FROM tickets WHERE user_id=%s ORDER BY created_at DESC",
                        (user["sub"],))
        rows = cur.fetchall()
    conn.close()
    return render_template("tickets.html", tickets=rows, me=user)


@app.route("/tickets/new", methods=["GET", "POST"])
@kc.login_required
def new_ticket():
    if request.method == "POST":
        user = session["user"]
        conn = db()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tickets (user_id, username, title, description, priority)
                VALUES (%s,%s,%s,%s,%s)
            """, (
                user["sub"], user["preferred_username"],
                request.form["title"], request.form["description"],
                request.form.get("priority", "normal"),
            ))
        conn.commit()
        conn.close()
        flash("Ticket créé")
        return redirect(url_for("tickets"))
    return render_template("new_ticket.html", me=session["user"])


@app.route("/tickets/<int:tid>", methods=["GET", "POST"])
@kc.login_required
def ticket_detail(tid):
    user = session["user"]
    conn = db()

    if request.method == "POST":
        # ajout d'un commentaire
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO comments (ticket_id, user_id, username, content)
                VALUES (%s,%s,%s,%s)
            """, (tid, user["sub"], user["preferred_username"], request.form["content"]))
        conn.commit()

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM tickets WHERE id=%s", (tid,))
        ticket = cur.fetchone()
        cur.execute("SELECT * FROM comments WHERE ticket_id=%s ORDER BY created_at", (tid,))
        comments = cur.fetchall()
    conn.close()

    if not ticket:
        return "Ticket introuvable", 404
    # Contrôle d'accès simple
    if ticket["user_id"] != user["sub"] and \
       "admin" not in user["roles"] and "support" not in user["roles"]:
        return "Accès refusé", 403

    return render_template("ticket_detail.html", ticket=ticket, comments=comments, me=user)


@app.route("/tickets/<int:tid>/status", methods=["POST"])
@kc.login_required
def update_status(tid):
    user = session["user"]
    if "admin" not in user["roles"] and "support" not in user["roles"]:
        return "Forbidden", 403
    new_status = request.form["status"]
    conn = db()
    with conn.cursor() as cur:
        cur.execute("UPDATE tickets SET status=%s, updated_at=NOW() WHERE id=%s",
                    (new_status, tid))
    conn.commit()
    conn.close()
    return redirect(url_for("ticket_detail", tid=tid))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
