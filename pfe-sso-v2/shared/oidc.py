"""
shared/oidc.py
--------------
Middleware OIDC minimaliste pour Flask + Keycloak.

Pourquoi ce fichier existe :
    Les 3 apps font la même chose pour s'authentifier (rediriger vers Keycloak,
    récupérer un code, l'échanger contre un token, lire les rôles). Plutôt que
    de copier-coller, on factorise ici.

Choix de simplification :
    - On ne vérifie PAS la signature JWT côté apps (Keycloak fait foi).
      Pour un vrai prod, il faudrait utiliser python-jose avec le JWKS.
    - Pas de PKCE : flow Authorization Code classique avec client_secret.
"""

import os
import json
import base64
import functools
from urllib.parse import urlencode

import requests
from flask import redirect, session, request, abort, g


class OIDCConfig:
    """Configuration OIDC lue depuis l'environnement."""

    def __init__(self):
        self.client_id = os.environ["OIDC_CLIENT_ID"]
        self.client_secret = os.environ["OIDC_CLIENT_SECRET"]
        self.issuer = os.environ["OIDC_ISSUER"]
        self.redirect_uri = os.environ["OIDC_REDIRECT_URI"]

        # URL interne (container -> container) pour les appels serveur->serveur
        self.token_url = f"{self.issuer}/protocol/openid-connect/token"

        # URL publique (vue depuis le navigateur de l'utilisateur)
        public_ip = os.environ.get("SERVER_IP", "localhost")
        public_issuer = self.issuer.replace("keycloak:8080", f"{public_ip}:8080")
        self.public_auth_url = f"{public_issuer}/protocol/openid-connect/auth"
        self.public_logout_url = f"{public_issuer}/protocol/openid-connect/logout"


_config = None


def init_oidc(app):
    """À appeler une fois au démarrage de l'app Flask."""
    global _config
    _config = OIDCConfig()
    app.config["OIDC"] = _config


def login_redirect():
    """Redirige le navigateur vers la page de login Keycloak."""
    params = {
        "client_id": _config.client_id,
        "redirect_uri": _config.redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
    }
    return redirect(f"{_config.public_auth_url}?{urlencode(params)}")


def handle_callback():
    """
    Échange le code Keycloak contre des tokens.
    Retourne le payload de l'ID token (dict) ou None en cas d'échec.
    """
    code = request.args.get("code")
    if not code:
        abort(400, "Missing authorization code")

    response = requests.post(
        _config.token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _config.redirect_uri,
            "client_id": _config.client_id,
            "client_secret": _config.client_secret,
        },
        timeout=10,
    )
    if response.status_code != 200:
        abort(502, f"Token exchange failed: {response.text}")

    tokens = response.json()
    payload = _decode_jwt_payload(tokens["id_token"])

    session["user"] = {
        "sub": payload["sub"],
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "roles": payload.get("roles", []),
    }
    session["access_token"] = tokens.get("access_token")
    return payload


def _decode_jwt_payload(jwt_token):
    """Décode la 2e partie d'un JWT (sans vérif signature)."""
    payload_b64 = jwt_token.split(".")[1]
    # Padding base64
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def logout():
    """Déconnecte l'utilisateur côté app + côté Keycloak."""
    session.clear()
    port = os.environ.get("FLASK_PORT", "5001")
    public_ip = os.environ.get("SERVER_IP", "localhost")
    post_logout = f"http://{public_ip}:{port}/"
    return redirect(
        f"{_config.public_logout_url}"
        f"?post_logout_redirect_uri={post_logout}"
        f"&client_id={_config.client_id}"
    )


def get_current_user():
    return session.get("user")


def login_required(f):
    """Décorateur : redirige vers Keycloak si pas connecté."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not get_current_user():
            return login_redirect()
        g.user = get_current_user()
        return f(*args, **kwargs)
    return wrapper


def require_role(*allowed_roles):
    """Décorateur : 403 si l'utilisateur n'a aucun des rôles attendus."""
    def decorator(f):
        @functools.wraps(f)
        @login_required
        def wrapper(*args, **kwargs):
            user = get_current_user()
            if not any(role in user.get("roles", []) for role in allowed_roles):
                abort(403, "Accès refusé")
            return f(*args, **kwargs)
        return wrapper
    return decorator
