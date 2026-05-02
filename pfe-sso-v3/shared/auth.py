"""
shared/auth.py
==============
Authentification JWT côté API : vérifie le token Keycloak signé via JWKS.

Différence majeure avec les versions précédentes :
    - Les SPA s'authentifient directement avec Keycloak (Authorization Code + PKCE)
    - Elles envoient le JWT dans le header Authorization
    - Les API VERIFIENT la signature avec la clé publique de Keycloak (JWKS)

C'est le pattern standard "Backend For Frontend" + JWT bearer.
"""
import os
from typing import List
from functools import lru_cache

import httpx
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError


bearer_scheme = HTTPBearer(auto_error=True)


@lru_cache(maxsize=1)
def _get_jwks() -> dict:
    """Récupère les clés publiques de Keycloak (cache permanent une fois chargé)."""
    issuer = os.environ["OIDC_ISSUER_INTERNAL"]
    url = f"{issuer}/protocol/openid-connect/certs"
    response = httpx.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def _find_key(kid: str) -> dict:
    """Trouve la clé publique correspondant au 'kid' du JWT."""
    for key in _get_jwks()["keys"]:
        if key["kid"] == kid:
            return key
    # Cache invalidé : la clé a peut-être changé après une rotation
    _get_jwks.cache_clear()
    for key in _get_jwks()["keys"]:
        if key["kid"] == kid:
            return key
    raise HTTPException(status_code=401, detail="Unknown signing key")


def verify_token(token: str) -> dict:
    """
    Vérifie la signature, l'expiration et l'issuer du JWT.
    Retourne le payload décodé.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
        key = _find_key(unverified_header["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=[unverified_header["alg"]],
            # Pour audience, Keycloak utilise 'account' par défaut, on relâche
            options={"verify_aud": False},
            issuer=os.environ["OIDC_ISSUER_INTERNAL"],
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Dépendance FastAPI à injecter dans les routes protégées."""
    payload = verify_token(creds.credentials)
    roles = payload.get("realm_access", {}).get("roles", [])
    return {
        "sub": payload["sub"],
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "roles": roles,
    }


def require_roles(*allowed: str):
    """Factory de dépendance pour exiger un ou plusieurs rôles."""
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if not any(r in user["roles"] for r in allowed):
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of: {allowed}"
            )
        return user
    return checker
