"""
APP 3 : Dashboard Admin Sécurité
=================================
- Logs temps réel (auth_events)
- Alertes ML (ml_alerts)
- Stats : top IPs, taux d'échec, géoloc
- API JSON pour rafraîchir le dashboard côté navigateur
"""
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, request, session, url_for, jsonify
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
        dbname=os.getenv("DB_NAME", "logsdb"),
    )


# ========== Auth ==========
@app.route("/")
def index():
    if "user" not in session:
        return render_template("login.html")
    return redirect(url_for("dashboard"))


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
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(kc.logout_url(url_for("index", _external=True)))


# ========== Dashboard ==========
@app.route("/dashboard")
@kc.role_required("admin")
def dashboard():
    return render_template("dashboard.html", me=session["user"])


# ========== APIs JSON consommées par le dashboard ==========
@app.route("/api/stats")
@kc.role_required("admin")
def api_stats():
    """Statistiques globales sur la dernière heure."""
    since = datetime.now() - timedelta(hours=1)
    conn = db()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT COUNT(*) AS n FROM auth_events WHERE event_time >= %s", (since,))
        total = cur.fetchone()["n"]

        cur.execute("""
            SELECT COUNT(*) AS n FROM auth_events
            WHERE event_time >= %s AND (event_type LIKE '%%ERROR%%' OR error IS NOT NULL)
        """, (since,))
        failures = cur.fetchone()["n"]

        cur.execute("""
            SELECT COUNT(*) AS n FROM auth_events
            WHERE event_time >= %s AND event_type = 'LOGIN'
        """, (since,))
        success = cur.fetchone()["n"]

        cur.execute("SELECT COUNT(*) AS n FROM ml_alerts WHERE detected_at >= %s", (since,))
        alerts = cur.fetchone()["n"]
    conn.close()
    return jsonify({"total": total, "failures": failures,
                    "success": success, "alerts": alerts})


@app.route("/api/events")
@kc.role_required("admin")
def api_events():
    """Derniers événements (50)."""
    conn = db()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT event_time, event_type, username, ip_address, country, error
            FROM auth_events ORDER BY event_time DESC LIMIT 50
        """)
        rows = cur.fetchall()
    conn.close()
    for r in rows:
        r["event_time"] = r["event_time"].strftime("%H:%M:%S")
    return jsonify(rows)


@app.route("/api/top_ips")
@kc.role_required("admin")
def api_top_ips():
    """Top 10 IPs avec le plus d'échecs (dernière heure)."""
    since = datetime.now() - timedelta(hours=1)
    conn = db()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT ip_address, country,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE event_type LIKE '%%ERROR%%' OR error IS NOT NULL) AS fails
            FROM auth_events
            WHERE event_time >= %s AND ip_address IS NOT NULL
            GROUP BY ip_address, country
            ORDER BY fails DESC LIMIT 10
        """, (since,))
        rows = cur.fetchall()
    conn.close()
    return jsonify(rows)


@app.route("/api/alerts")
@kc.role_required("admin")
def api_alerts():
    """Dernières alertes ML."""
    conn = db()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT detected_at, ip_address, score, reason, features
            FROM ml_alerts ORDER BY detected_at DESC LIMIT 20
        """)
        rows = cur.fetchall()
    conn.close()
    for r in rows:
        r["detected_at"] = r["detected_at"].strftime("%Y-%m-%d %H:%M:%S")
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
