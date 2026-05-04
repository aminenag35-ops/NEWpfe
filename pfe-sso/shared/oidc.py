"""
shared/oidc.py – Middleware OIDC commun aux 3 applications
- Gère le flux Authorization Code avec Keycloak
- Vérifie les tokens JWT
- Extrait identité + rôles
- Fournit un décorateur @require_role(...)
"""

import os
import json
import time
import functools
import requests
from urllib.parse import urlencode
from flask import redirect, session, request, g, abort, url_for


# ---------------------------------------------------------------------------
# Configuration OIDC (lue depuis les variables d'environnement)
# ---------------------------------------------------------------------------
class OIDCConfig:
    def __init__(self):
        self.client_id = os.environ["OIDC_CLIENT_ID"]
        self.client_secret = os.environ["OIDC_CLIENT_SECRET"]
        self.issuer = os.environ["OIDC_ISSUER"]
        self.redirect_uri = os.environ["OIDC_REDIRECT_URI"]

        # Points de terminaison OIDC (dérivés de l'issuer)
        self.auth_url = f"{self.issuer}/protocol/openid-connect/auth"
        self.token_url = f"{self.issuer}/protocol/openid-connect/token"
        self.userinfo_url = f"{self.issuer}/protocol/openid-connect/userinfo"
        self.logout_url = f"{self.issuer}/protocol/openid-connect/logout"
        self.jwks_url = f"{self.issuer}/protocol/openid-connect/certs"

        # URL publique (vue depuis le navigateur) — lit SERVER_IP depuis l'env
        self.public_ip = os.environ.get("SERVER_IP", "localhost")
        self.public_issuer = self.issuer.replace("keycloak:8080", f"{self.public_ip}:8080")
        self.public_auth_url = self.auth_url.replace("keycloak:8080", f"{self.public_ip}:8080")
        self.public_logout_url = self.logout_url.replace("keycloak:8080", f"{self.public_ip}:8080")


# ---------------------------------------------------------------------------
# Initialisation Flask
# ---------------------------------------------------------------------------
_oidc_config = None


def init_oidc(app):
    """Initialise la config OIDC et enregistre le before_request."""
    global _oidc_config
    _oidc_config = OIDCConfig()
    app.config["OIDC"] = _oidc_config


def get_oidc_config():
    return _oidc_config


# ---------------------------------------------------------------------------
# Flux Authorization Code : redirection vers Keycloak
# ---------------------------------------------------------------------------
def login_redirect():
    """Redirige l'utilisateur vers la page de login Keycloak."""
    cfg = get_oidc_config()
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
    }
    return redirect(f"{cfg.public_auth_url}?{urlencode(params)}")


# ---------------------------------------------------------------------------
# Callback : échange du code contre des tokens
# ---------------------------------------------------------------------------
def handle_callback():
    """Échange le code d'autorisation contre access_token + id_token."""
    cfg = get_oidc_config()
    code = request.args.get("code")
    if not code:
        abort(400, "Missing authorization code")

    # Appel au token endpoint (serveur -> serveur, donc URL interne)
    resp = requests.post(
        cfg.token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cfg.redirect_uri,
            "client_id": cfg.client_id,
            "client_secret": cfg.client_secret,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        abort(502, f"Token exchange failed: {resp.text}")

    tokens = resp.json()

    # Décoder le token (sans vérif signature côté app – Keycloak fait foi)
    import base64
    id_token = tokens.get("id_token", "")
    payload_b64 = id_token.split(".")[1]
    # Ajouter padding
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))

    # Extraire les informations utilisateur
    session["user"] = {
        "sub": payload.get("sub"),
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "name": payload.get("name", payload.get("preferred_username")),
        "roles": payload.get("roles", []),
    }
    session["access_token"] = tokens.get("access_token")
    session["refresh_token"] = tokens.get("refresh_token")

    return redirect("/")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
def logout():
    """Déconnecte l'utilisateur (session locale + Keycloak)."""
    cfg = get_oidc_config()
    session.clear()
    app_port = os.environ.get("FLASK_PORT", "5001")
    public_ip = os.environ.get("SERVER_IP", "localhost")
    post_logout = f"http://{public_ip}:{app_port}/"
    return redirect(
        f"{cfg.public_logout_url}?post_logout_redirect_uri={post_logout}&client_id={cfg.client_id}"
    )


# ---------------------------------------------------------------------------
# Helpers : utilisateur courant
# ---------------------------------------------------------------------------
def get_current_user():
    """Retourne le dict utilisateur depuis la session, ou None."""
    return session.get("user")


def is_authenticated():
    return get_current_user() is not None


# ---------------------------------------------------------------------------
# Décorateurs de protection
# ---------------------------------------------------------------------------
def login_required(f):
    """Redirige vers Keycloak si l'utilisateur n'est pas connecté."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not is_authenticated():
            return login_redirect()
        g.user = get_current_user()
        return f(*args, **kwargs)
    return wrapper


def require_role(*allowed_roles):
    """Vérifie que l'utilisateur possède au moins un des rôles listés."""
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            user = get_current_user()
            user_roles = user.get("roles", [])
            if not any(r in user_roles for r in allowed_roles):
                abort(403, "Accès refusé – rôle insuffisant")
            return f(*args, **kwargs)
        return wrapper
    return decorator
