"""
App 3 — Dashboard de supervision sécurité
=========================================

Rôle : afficher en temps réel les alertes générées par le ML, les statistiques,
et la liste des IPs bloquées.

Choix techniques :
    - Flask + Flask-SocketIO pour le push WebSocket vers le navigateur.
    - Un thread d'arrière-plan consomme `security.alerts` et émet sur le WS.
    - Pas de polling : le dashboard reçoit chaque alerte en quelques ms.
"""

import os
import sys
import threading
import logging

sys.path.insert(0, "/app/shared")

from flask import Flask, jsonify, render_template_string
from flask_socketio import SocketIO

from oidc import init_oidc, login_redirect, handle_callback, logout, require_role
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
    return "<script>location='/'</script>"


@app.route("/logout")
def do_logout():
    return logout()


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
    # JSON-isable
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
# Page d'accueil minimaliste (l'UI riche n'est pas demandée)
# -----------------------------------------------------------------------------

INDEX_TEMPLATE = """
<!doctype html>
<title>Dashboard Sécurité</title>
<h1>Dashboard Sécurité</h1>
<div id="alerts"></div>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<script>
const socket = io();
socket.on('new_alert', (alert) => {
    const div = document.createElement('div');
    div.style.padding = '8px';
    div.style.margin = '4px';
    div.style.border = '1px solid red';
    div.textContent = `[${alert.severity}] ${alert.alert_type} — `
                    + `${alert.username} from ${alert.ip_address}`;
    document.getElementById('alerts').prepend(div);
});
</script>
"""


@app.route("/")
def index():
    return render_template_string(INDEX_TEMPLATE)


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5003))
    socketio.run(app, host="0.0.0.0", port=port, debug=False,
                 allow_unsafe_werkzeug=True)
