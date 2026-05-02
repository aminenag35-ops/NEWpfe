"""
App 2 — Tickets + User Profile
==============================

Rôle : c'est l'application qui simule l'activité utilisateur. Chaque action
significative (surtout login / logout) est publiée sur Kafka pour que le ML
puisse l'analyser en temps réel.

Endpoints clés :
    /            -> liste des tickets
    /login       -> redirige vers Keycloak
    /callback    -> retour de Keycloak + publication d'un événement Kafka
    /logout      -> déconnexion + publication d'un événement
    /ticket/new  -> création d'un ticket
    /api/event   -> endpoint utilisé par le simulateur de trafic
"""

import os
import sys
import logging

sys.path.insert(0, "/app/shared")

from flask import Flask, request, redirect, jsonify, render_template_string

from oidc import (
    init_oidc, login_redirect, handle_callback, logout,
    login_required, get_current_user
)
from kafka_client import get_producer, publish_event
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
log = logging.getLogger("tickets")

app = Flask(__name__)
app.secret_key = os.environ["APP_SECRET_KEY"]
init_oidc(app)

# Producteur Kafka : un seul pour toute la durée de vie du process
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
producer = get_producer()


def db():
    """Ouvre une connexion PostgreSQL avec curseur dict."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    return conn


def client_ip():
    """Récupère l'IP du client (gère le cas X-Forwarded-For)."""
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else request.remote_addr


# ----------------------------------------------------------------------------
# Authentification (avec publication Kafka)
# ----------------------------------------------------------------------------

@app.route("/login")
def login():
    return login_redirect()


@app.route("/callback")
def callback():
    """
    Retour de Keycloak. C'EST L'ENDROIT CLÉ : on publie un événement
    'login_success' sur Kafka dès qu'un utilisateur arrive ici avec un code
    valide.
    """
    handle_callback()  # met l'utilisateur en session
    user = get_current_user()
    if user:
        publish_event(
            producer, KAFKA_TOPIC,
            event_type="login_success",
            username=user["username"],
            ip_address=client_ip(),
            success=True,
            details={"app": "tickets"},
        )
        log.info("LOGIN_SUCCESS user=%s ip=%s", user["username"], client_ip())
    return redirect("/")


@app.route("/logout")
def do_logout():
    user = get_current_user()
    if user:
        publish_event(
            producer, KAFKA_TOPIC,
            event_type="logout",
            username=user["username"],
            ip_address=client_ip(),
        )
    return logout()


# ----------------------------------------------------------------------------
# Endpoint utilisé par le simulateur de trafic
# ----------------------------------------------------------------------------

@app.route("/api/event", methods=["POST"])
def api_event():
    """
    Permet au simulateur d'injecter directement un événement.
    On ne le passe PAS à Kafka via Keycloak (qui est lent), on le publie
    directement. C'est volontaire : on simule le résultat final.

    Pas de protection ici car c'est un outil de test interne ; en prod il
    faudrait une auth machine-to-machine ou supprimer cet endpoint.
    """
    data = request.get_json(silent=True) or {}
    publish_event(
        producer, KAFKA_TOPIC,
        event_type=data.get("event_type", "login_failed"),
        username=data.get("username", "unknown"),
        ip_address=data.get("ip_address", client_ip()),
        success=data.get("success", False),
        details=data.get("details", {}),
    )
    return jsonify({"status": "published"}), 202


# ----------------------------------------------------------------------------
# UI minimaliste (le sujet n'a pas demandé d'UI, juste une page de test)
# ----------------------------------------------------------------------------

HOME_TEMPLATE = """
<!doctype html>
<title>Tickets</title>
<h1>App Tickets</h1>
{% if user %}
  <p>Connecté : {{ user.username }} ({{ user.roles|join(', ') }})</p>
  <form method="POST" action="/ticket/new">
    <input name="title" placeholder="Titre" required>
    <input name="description" placeholder="Description">
    <button>Créer</button>
  </form>
  <ul>
    {% for t in tickets %}
      <li>#{{ t.id }} — {{ t.title }} ({{ t.status }})</li>
    {% endfor %}
  </ul>
  <a href="/logout">Déconnexion</a>
{% else %}
  <a href="/login">Connexion via Keycloak</a>
{% endif %}
"""


@app.route("/")
@login_required
def home():
    user = get_current_user()
    with db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM tickets.tickets WHERE created_by = %s "
                "ORDER BY created_at DESC LIMIT 20",
                (user["sub"],)
            )
            tickets = cur.fetchall()
    return render_template_string(HOME_TEMPLATE, user=user, tickets=tickets)


@app.route("/ticket/new", methods=["POST"])
@login_required
def new_ticket():
    user = get_current_user()
    title = request.form.get("title", "").strip()
    if not title:
        return "Title required", 400

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tickets.tickets (title, description, created_by) "
                "VALUES (%s, %s, %s)",
                (title, request.form.get("description", ""), user["sub"])
            )

    # On publie aussi cet événement pour la traçabilité (mais pas critique)
    publish_event(
        producer, KAFKA_TOPIC,
        event_type="ticket_created",
        username=user["username"],
        ip_address=client_ip(),
        details={"title": title},
    )
    return redirect("/")


if __name__ == "__main__":
    port = int(os.environ.get("FLASK_PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=False)
