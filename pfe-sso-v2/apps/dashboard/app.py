"""
App 3 — Dashboard de supervision sécurité (API-only backend)
=============================================================

Rôle : fournir en temps réel les alertes générées par le ML via Socket.IO,
les statistiques, et la liste des IPs bloquées.

Choix techniques :
    - Flask + Flask-SocketIO pour le push WebSocket vers le navigateur React.
    - Un thread d'arrière-plan consomme `security.alerts` et émet sur le WS.
    - Pas de polling : le dashboard reçoit chaque alerte en quelques ms.
    - React frontend (Vite) servi depuis /app/static/dist.
"""

import os
import sys
import threading
import logging

sys.path.insert(0, "/app/shared")

from flask import Flask, jsonify, redirect, send_from_directory
from flask_socketio import SocketIO

from oidc import init_oidc, login_redirect, handle_callback, logout, require_role, get_current_user
from kafka_client import get_consumer
import psycopg2
import psycopg2.extras
import redis

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("dashboard")

app = Flask(__name__)
app.secret_key = os.environ["APP_SECRET_KEY"]
init_oidc(app)

# WebSocket : threading mode pour rester simple (pas d'eventlet/gevent)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "security.alerts")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "dist")


# -----------------------------------------------------------------------------
# Thread Kafka -> WebSocket
# -----------------------------------------------------------------------------

def kafka_to_websocket_pump():
    """
    Tourne en thread d'arrière-plan : consomme les alertes du topic Kafka et
    les pousse via Socket.IO à tous les clients connectés.
    """
    consumer = get_consumer(TOPIC_ALERTS, group_id="dashboard-v1")
    log.info("WebSocket pump started, listening on %s", TOPIC_ALERTS)
    for msg in consumer:
        try:
            socketio.emit("new_alert", msg.value)
            log.info("Alert pushed: %s / %s",
                     msg.value.get("alert_type"), msg.value.get("username"))
        except Exception as e:
            log.exception("Failed to push alert: %s", e)


threading.Thread(target=kafka_to_websocket_pump, daemon=True).start()


# -----------------------------------------------------------------------------
# Endpoints OIDC
# -----------------------------------------------------------------------------

@app.route("/login")
def login():
    return login_redirect()


@app.route("/callback")
def callback():
    handle_callback()
    return redirect("/")


@app.route("/logout")
def do_logout():
    return logout()


# -----------------------------------------------------------------------------
# API — current user
# -----------------------------------------------------------------------------

@app.route("/api/me")
def api_me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user)


# -----------------------------------------------------------------------------
# API REST (statistiques + liste alertes)
# -----------------------------------------------------------------------------

def db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    return conn


@app.route("/api/stats")
@require_role("admin", "manager")
def api_stats():
    """Renvoie un résumé des alertes des dernières 24h."""
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT alert_type, severity, COUNT(*) AS count
                FROM security.alerts
                WHERE timestamp >= NOW() - INTERVAL '24 hours'
                GROUP BY alert_type, severity
                ORDER BY count DESC
            """)
            stats = cur.fetchall()
    return jsonify(stats)


@app.route("/api/alerts/recent")
@require_role("admin", "manager")
def api_recent_alerts():
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM security.alerts "
                "ORDER BY timestamp DESC LIMIT 50"
            )
            alerts = cur.fetchall()
    for a in alerts:
        a["timestamp"] = a["timestamp"].isoformat()
    return jsonify(alerts)


@app.route("/api/blocked-ips")
@require_role("admin", "manager")
def api_blocked_ips():
    """Liste les IPs actuellement bloquées dans Redis."""
    r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    blocked = []
    for key in r.scan_iter("blocked_ip:*"):
        ip = key.split(":", 1)[1]
        ttl = r.ttl(key)
        reason = r.get(key)
        blocked.append({"ip": ip, "ttl_seconds": ttl, "reason": reason})
    return jsonify(blocked)


# -----------------------------------------------------------------------------
# React SPA — catch-all (doit être en dernier)
# -----------------------------------------------------------------------------

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    if path and os.path.exists(os.path.join(STATIC_DIR, path)):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5003))
    socketio.run(app, host="0.0.0.0", port=port, debug=False,
                 allow_unsafe_werkzeug=True)
