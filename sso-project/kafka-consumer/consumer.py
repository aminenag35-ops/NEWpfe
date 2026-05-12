"""
Consumer Kafka -> PostgreSQL
============================
Lit les événements Keycloak depuis le topic Kafka et les insère
dans la table auth_events de la base logsdb.

Code volontairement simple : 1 message = 1 INSERT.
Pour un volume élevé on batcherait, mais ici la lisibilité prime.
"""

import os
import json
import time
import logging
from datetime import datetime

from kafka import KafkaConsumer
import psycopg2
from psycopg2.extras import Json

# --- Config (variables d'env passées par docker-compose) ---
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC     = os.getenv("KAFKA_TOPIC", "keycloak-events")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PWD  = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "logsdb")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("consumer")


def connect_db():
    """Reconnexion automatique en cas d'échec (utile au démarrage)."""
    while True:
        try:
            conn = psycopg2.connect(
                host=DB_HOST, user=DB_USER, password=DB_PWD, dbname=DB_NAME
            )
            conn.autocommit = True
            log.info("Connecté à PostgreSQL")
            return conn
        except Exception as e:
            log.warning(f"Postgres pas prêt : {e}, retry dans 3s...")
            time.sleep(3)


def connect_kafka():
    """Pareil : on attend Kafka."""
    while True:
        try:
            consumer = KafkaConsumer(
                KAFKA_TOPIC,
                bootstrap_servers=[KAFKA_BOOTSTRAP],
                auto_offset_reset="earliest",
                group_id="auth-events-consumer",
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            )
            log.info(f"Connecté à Kafka topic={KAFKA_TOPIC}")
            return consumer
        except Exception as e:
            log.warning(f"Kafka pas prêt : {e}, retry dans 3s...")
            time.sleep(3)


def fake_geoip(ip: str) -> str:
    """
    Mini résolution GeoIP "factice" pour la démo.
    Pour de la vraie géoloc : utiliser maxminddb + base GeoLite2.
    Ici on retourne juste un pays selon le préfixe pour avoir des données.
    """
    if not ip:
        return "Unknown"
    if ip.startswith("10.") or ip.startswith("172.") or ip.startswith("192.168") \
       or ip.startswith("127.") or ip == "localhost":
        return "LAN"
    # Préfixes inventés pour la simulation d'attaques
    if ip.startswith("203."): return "CN"
    if ip.startswith("185."): return "RU"
    if ip.startswith("196."): return "TN"
    if ip.startswith("41."):  return "MA"
    return "??"


def insert_event(conn, msg: dict):
    """Insère un événement Keycloak en base."""
    details = msg.get("details") or {}
    event_time = datetime.fromtimestamp(msg["time"] / 1000.0) if msg.get("time") else datetime.now()

    sql = """
        INSERT INTO auth_events (
            event_time, event_type, realm_id, client_id,
            user_id, username, ip_address, user_agent,
            error, session_id, country, raw_json
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            event_time,
            msg.get("type"),
            msg.get("realmId"),
            msg.get("clientId"),
            msg.get("userId"),
            details.get("username"),
            msg.get("ipAddress"),
            details.get("user_agent") or details.get("userAgent"),
            msg.get("error"),
            msg.get("sessionId"),
            fake_geoip(msg.get("ipAddress")),
            Json(msg),
        ))


def main():
    conn = connect_db()
    consumer = connect_kafka()

    log.info("Consumer démarré, en attente de messages...")
    for record in consumer:
        try:
            event = record.value
            insert_event(conn, event)
            log.info(f"[{event.get('type'):<20}] user={event.get('details',{}).get('username','-')} "
                     f"ip={event.get('ipAddress')} err={event.get('error')}")
        except Exception as e:
            log.error(f"Erreur traitement message : {e}")


if __name__ == "__main__":
    main()
