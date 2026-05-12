"""
Module commun pour l'auth OIDC avec Keycloak.
Utilisé par les 3 apps Flask. Volontairement minimaliste.
"""
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

import requests
from flask import session, redirect, request, url_for, abort

# --- Variables d'env (passées par docker-compose) ---
# URL interne (entre conteneurs) : pour les appels backend
KC_URL    = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
# URL publique (vue par le navigateur Windows) : pour les redirections
KC_PUBLIC = os.getenv("KEYCLOAK_PUBLIC_URL", "http://localhost:8080")
REALM     = os.getenv("KEYCLOAK_REALM", "sso-demo")
CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")


def _endpoint(public: bool, path: str) -> str:
    base = KC_PUBLIC if public else KC_URL
    return f"{base}/realms/{REALM}/protocol/openid-connect{path}"


def login_url(redirect_uri: str) -> str:
    """Construit l'URL d'autorisation Keycloak (vue par le navigateur)."""
    state = secrets.token_urlsafe(16)
    session["oauth_state"] = state
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "scope":         "openid profile email",
        "redirect_uri":  redirect_uri,
        "state":         state,
    }
    return _endpoint(public=True, path="/auth") + "?" + urlencode(params)


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Échange le code d'autorisation contre des tokens (appel backend)."""
    r = requests.post(
        _endpoint(public=False, path="/token"),
        data={
            "grant_type":   "authorization_code",
            "code":         code,
            "redirect_uri": redirect_uri,
            "client_id":    CLIENT_ID,
            "client_secret":CLIENT_SECRET,
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def userinfo(access_token: str) -> dict:
    """Récupère les infos utilisateur via le token."""
    r = requests.get(
        _endpoint(public=False, path="/userinfo"),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def logout_url(redirect_uri: str) -> str:
    """URL de déconnexion Keycloak."""
    params = {"client_id": CLIENT_ID, "post_logout_redirect_uri": redirect_uri}
    return _endpoint(public=True, path="/logout") + "?" + urlencode(params)


def login_required(f):
    """Décorateur : redirige vers login si pas authentifié."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(role: str):
    """Décorateur : exige un rôle Keycloak (realm role)."""
    def deco(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user" not in session:
                return redirect(url_for("login"))
            roles = session["user"].get("roles", [])
            if role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return deco


def parse_roles_from_token(token_data: dict) -> list:
    """
    Extrait les rôles realm depuis l'access_token (JWT).
    On décode sans vérifier la signature (ok pour démo PFE).
    Pour la prod, utiliser python-jose avec la JWK de Keycloak.
    """
    import base64, json
    try:
        payload = token_data["access_token"].split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded.get("realm_access", {}).get("roles", [])
    except Exception:
        return []


def admin_token() -> str:
    """
    Récupère un token admin pour piloter Keycloak via son Admin REST API.
    Utilisé par l'app admin pour CRUD users/roles.
    """
    r = requests.post(
        f"{KC_URL}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id":  "admin-cli",
            "username":   os.getenv("KC_ADMIN_USER", "admin"),
            "password":   os.getenv("KC_ADMIN_PASSWORD", "admin"),
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def admin_api(method: str, path: str, **kwargs):
    """Helper pour appeler l'Admin REST API Keycloak."""
    token = admin_token()
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {token}"
    url = f"{KC_URL}/admin/realms/{REALM}{path}"
    return requests.request(method, url, headers=headers, timeout=10, **kwargs)
