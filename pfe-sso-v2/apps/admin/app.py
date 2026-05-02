"""
App 1 — Administration & sécurité (API-only backend)
=====================================================

Rôle :
    - Lister, bloquer/débloquer les utilisateurs.
    - Consulter le journal d'audit.
    - Voir les alertes générées par le ML.
    - Lister et débloquer manuellement les IPs bloquées dans Redis.

Réservé aux comptes ayant le rôle Keycloak `admin`.
React frontend (Vite) servi depuis /app/static/dist.
"""

import os
import sys
import logging

sys.path.insert(0, "/app/shared")

from flask import Flask, request, jsonify, redirect, send_from_directory

from oidc import (
    init_oidc, login_redirect, handle_callback, logout,
    require_role, get_current_user
)
import psycopg2
import psycopg2.extras
import redis as redis_module

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("admin")

app = Flask(__name__)
app.secret_key = os.environ["APP_SECRET_KEY"]
init_oidc(app)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static", "dist")


def db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    return conn


def redis_conn():
    return redis_module.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


# -----------------------------------------------------------------------------
# OIDC
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
# Gestion utilisateurs
# -----------------------------------------------------------------------------

@app.route("/api/users")
@require_role("admin")
def list_users():
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM auth.users ORDER BY created_at DESC")
            users = cur.fetchall()
    for u in users:
        u["created_at"] = u["created_at"].isoformat()
        if u["blocked_at"]:
            u["blocked_at"] = u["blocked_at"].isoformat()
    return jsonify(users)


@app.route("/api/users/<int:user_id>/block", methods=["POST"])
@require_role("admin")
def block_user(user_id):
    reason = (request.json or {}).get("reason", "manual block")
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.users SET is_blocked = TRUE, blocked_at = NOW(), "
                "blocked_reason = %s WHERE id = %s",
                (reason, user_id)
            )
    log.info("User %d blocked: %s", user_id, reason)
    return jsonify({"status": "blocked"})


@app.route("/api/users/<int:user_id>/unblock", methods=["POST"])
@require_role("admin")
def unblock_user(user_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE auth.users SET is_blocked = FALSE, blocked_at = NULL, "
                "blocked_reason = NULL WHERE id = %s",
                (user_id,)
            )
    return jsonify({"status": "unblocked"})


# -----------------------------------------------------------------------------
# Audit & alertes
# -----------------------------------------------------------------------------

@app.route("/api/audit")
@require_role("admin")
def audit():
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM auth.audit_log "
                "ORDER BY timestamp DESC LIMIT 100"
            )
            rows = cur.fetchall()
    for r in rows:
        r["timestamp"] = r["timestamp"].isoformat()
    return jsonify(rows)


@app.route("/api/alerts")
@require_role("admin")
def alerts():
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM security.alerts "
                "ORDER BY timestamp DESC LIMIT 100"
            )
            rows = cur.fetchall()
    for r in rows:
        r["timestamp"] = r["timestamp"].isoformat()
    return jsonify(rows)


# -----------------------------------------------------------------------------
# Gestion des IPs bloquées (Redis)
# -----------------------------------------------------------------------------

@app.route("/api/blocked-ips")
@require_role("admin")
def list_blocked_ips():
    r = redis_conn()
    blocked = []
    for key in r.scan_iter("blocked_ip:*"):
        ip = key.split(":", 1)[1]
        ttl = r.ttl(key)
        reason = r.get(key)
        blocked.append({"ip": ip, "ttl_seconds": ttl, "reason": reason})
    return jsonify(blocked)


@app.route("/api/blocked-ips/<ip>", methods=["DELETE"])
@require_role("admin")
def unblock_ip(ip):
    r = redis_conn()
    deleted = r.delete(f"blocked_ip:{ip}")
    return jsonify({"deleted": bool(deleted)})


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
    port = int(os.environ.get("FLASK_PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
