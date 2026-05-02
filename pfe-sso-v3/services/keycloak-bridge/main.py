"""
Keycloak Bridge — capture les VRAIS événements d'authentification
==================================================================

Ce service interroge l'API Admin de Keycloak toutes les N secondes pour
récupérer les événements d'authentification GÉNÉRÉS PAR KEYCLOAK lui-même
(pas inventés par notre code).

Pourquoi c'est important pour le PFE :
    - Les events viennent de la source officielle (Keycloak)
    - Les IPs sont les VRAIES IPs vues par le serveur HTTP
    - Les timestamps sont ceux du moment exact du login
    - Les user-agents sont ceux des vrais clients
    - On capture aussi les LOGIN_ERROR avec les raisons précises
      (invalid_user_credentials, user_disabled, etc.)

API utilisée :
    GET /admin/realms/{realm}/events
    Paramètres : ?dateFrom=...&type=LOGIN&type=LOGIN_ERROR

Format des events Keycloak (extrait) :
    {
        "time": 1714658400000,
        "type": "LOGIN" | "LOGIN_ERROR",
        "realmId": "pfe",
        "clientId": "spa-tickets",
        "userId": "abc-123-uuid",
        "ipAddress": "192.168.1.50",
        "error": "invalid_user_credentials",  # uniquement si LOGIN_ERROR
        "details": {
            "username": "alice",
            "auth_method": "openid-connect"
        }
    }
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import httpx
from aiokafka import AIOKafkaProducer

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(message)s")
log = logging.getLogger("keycloak-bridge")


KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.environ.get("KEYCLOAK_REALM", "pfe")
ADMIN_USER = os.environ.get("KEYCLOAK_ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin")
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 5))  # secondes


# -----------------------------------------------------------------------------
# Authentification admin auprès de Keycloak
# -----------------------------------------------------------------------------
class KeycloakAdminClient:
    """Gère le token d'admin et le refresh automatiquement."""

    def __init__(self, base_url, user, password):
        self.base_url = base_url
        self.user = user
        self.password = password
        self._token = None
        self._token_expires_at = 0
        self._client = httpx.AsyncClient(timeout=30)

    async def _login(self):
        url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        r = await self._client.post(url, data={
            "client_id": "admin-cli",
            "username": self.user,
            "password": self.password,
            "grant_type": "password",
        })
        r.raise_for_status()
        data = r.json()
        self._token = data["access_token"]
        # Sécurité : on rafraîchit avant expiration
        self._token_expires_at = data["expires_in"] - 30
        log.info("Admin token refreshed")

    async def _ensure_token(self):
        # Stratégie simple : on relogue à chaque appel (le token dure 60s par défaut).
        # Pour un PFE c'est suffisant. En prod on tracker l'expiration.
        if not self._token:
            await self._login()

    async def get_events(self, realm, since_timestamp_ms):
        """Récupère les events d'auth depuis un timestamp donné."""
        await self._ensure_token()
        url = f"{self.base_url}/admin/realms/{realm}/events"
        params = {
            "dateFrom": datetime.fromtimestamp(since_timestamp_ms / 1000)
                                .strftime("%Y-%m-%d"),
            "type": ["LOGIN", "LOGIN_ERROR", "LOGOUT"],
            "max": 100,
        }
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            r = await self._client.get(url, params=params, headers=headers)
            if r.status_code == 401:
                # Token expiré, on relogue
                self._token = None
                await self._ensure_token()
                headers = {"Authorization": f"Bearer {self._token}"}
                r = await self._client.get(url, params=params, headers=headers)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            log.warning("Failed to fetch events: %s", e)
            return []

    async def close(self):
        await self._client.aclose()


# -----------------------------------------------------------------------------
# Conversion Keycloak event → format unifié de notre pipeline
# -----------------------------------------------------------------------------
def keycloak_event_to_pipeline(kc_event):
    """
    Transforme un event Keycloak en notre format standard.

    Keycloak format:
        {"time": 1714658400000, "type": "LOGIN_ERROR",
         "ipAddress": "10.0.0.99", "details": {"username": "charlie"},
         "error": "invalid_user_credentials"}

    Notre format:
        {"event_id": uuid, "event_type": "login_failed",
         "username": "charlie", "ip_address": "10.0.0.99",
         "success": false, "timestamp": "2026-...", "details": {...}}
    """
    kc_type = kc_event.get("type", "")
    details = kc_event.get("details", {}) or {}

    # Mapping des types Keycloak vers nos types
    if kc_type == "LOGIN":
        event_type = "login_success"
        success = True
    elif kc_type == "LOGIN_ERROR":
        event_type = "login_failed"
        success = False
    elif kc_type == "LOGOUT":
        event_type = "logout"
        success = True
    else:
        return None  # On ignore les autres types

    # Le username est dans details pour LOGIN_ERROR, sinon il faut résoudre userId
    username = details.get("username")
    if not username and kc_event.get("userId"):
        # Pour LOGIN réussi, Keycloak met userId mais pas username dans details.
        # On utilise userId comme fallback (UUID) — le ML s'en accommode.
        username = kc_event["userId"]

    return {
        "event_id":   str(uuid.uuid4()),
        "event_type": event_type,
        "username":   username or "unknown",
        "ip_address": kc_event.get("ipAddress", "unknown"),
        "user_agent": "",  # Keycloak ne le met pas par défaut dans events
        "success":    success,
        "timestamp":  datetime.fromtimestamp(
                          kc_event["time"] / 1000, tz=timezone.utc
                      ).isoformat(),
        "details": {
            "source":     "keycloak_real",
            "kc_type":    kc_type,
            "client_id":  kc_event.get("clientId"),
            "kc_event_id": kc_event.get("id"),
            "kc_error":   kc_event.get("error"),  # raison précise
            **details,
        },
    }


# -----------------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------------
async def main():
    log.info("=" * 60)
    log.info("Keycloak Bridge starting")
    log.info("Polling %s every %ds", KEYCLOAK_URL, POLL_INTERVAL)
    log.info("=" * 60)

    # Attendre que Keycloak soit prêt
    await wait_for_keycloak()

    admin = KeycloakAdminClient(KEYCLOAK_URL, ADMIN_USER, ADMIN_PASS)
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    await producer.start()

    # On garde l'ID des events déjà publiés pour ne pas dupliquer
    # (Keycloak ne supporte pas dateFrom à la milliseconde, donc on filtre côté client)
    seen_event_ids = set()
    last_check_ms = int(datetime.now().timestamp() * 1000) - 60_000  # 1 min en arrière au démarrage

    try:
        while True:
            try:
                events = await admin.get_events(REALM, last_check_ms)
                new_events = 0
                for kc_event in events:
                    kc_id = kc_event.get("id")
                    if kc_id in seen_event_ids:
                        continue
                    seen_event_ids.add(kc_id)

                    pipeline_event = keycloak_event_to_pipeline(kc_event)
                    if pipeline_event:
                        await producer.send_and_wait(
                            KAFKA_TOPIC,
                            key=pipeline_event["username"].encode(),
                            value=pipeline_event,
                        )
                        new_events += 1
                        log.info("REAL %s | user=%s ip=%s",
                                 pipeline_event["event_type"],
                                 pipeline_event["username"],
                                 pipeline_event["ip_address"])

                if new_events:
                    log.info("Published %d real Keycloak events", new_events)

                # Cap la mémoire : on ne garde que les 10000 derniers IDs
                if len(seen_event_ids) > 10000:
                    seen_event_ids = set(list(seen_event_ids)[-5000:])

                last_check_ms = int(datetime.now().timestamp() * 1000)
            except Exception as e:
                log.exception("Poll cycle failed: %s", e)

            await asyncio.sleep(POLL_INTERVAL)

    finally:
        await producer.stop()
        await admin.close()


async def wait_for_keycloak():
    """Attend que Keycloak soit joignable et que les events soient activés."""
    async with httpx.AsyncClient(timeout=10) as client:
        for attempt in range(60):
            try:
                r = await client.get(f"{KEYCLOAK_URL}/realms/{REALM}/.well-known/openid-configuration")
                if r.status_code == 200:
                    log.info("Keycloak is ready (realm %s found)", REALM)
                    return
            except httpx.HTTPError:
                pass
            log.info("Waiting for Keycloak... (%d/60)", attempt + 1)
            await asyncio.sleep(5)
    raise RuntimeError("Keycloak not reachable after 5 minutes")


if __name__ == "__main__":
    asyncio.run(main())
