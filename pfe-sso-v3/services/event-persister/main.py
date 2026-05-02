"""
Event Persister — Kafka → PostgreSQL
=====================================

Ce service est l'incarnation du pattern "Kafka source de vérité" :

    1. Les apps NE persistent JAMAIS directement les événements d'auth en DB
    2. Elles publient sur Kafka (topic auth.events ou security.alerts)
    3. CE service consume les topics et matérialise les données en DB

Avantages :
    - Si la DB tombe, Kafka conserve les événements (rejouables)
    - On peut ajouter d'autres consumers (analytics, alerting, etc.) sans
      toucher au code des apps
    - La DB devient une vue dérivée, pas la source

Le service consume les DEUX topics dans des tasks parallèles.
"""
import asyncio
import json
import logging
import os
from datetime import datetime
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(message)s")
log = logging.getLogger("event-persister")

DATABASE_URL = os.environ["DATABASE_URL"]
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
TOPIC_EVENTS = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "security.alerts")

engine = create_async_engine(DATABASE_URL, pool_size=5)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


# -----------------------------------------------------------------------------
# Persister auth.events
# -----------------------------------------------------------------------------
async def persist_auth_event(session: AsyncSession, event: dict):
    """
    Insère un événement dans auth.events.
    Utilise event_id comme clé d'idempotence : si on reçoit deux fois
    le même message (rejeu Kafka), on ignore.
    """
    try:
        # ON CONFLICT DO NOTHING grâce à la contrainte UNIQUE sur event_id
        await session.execute(text("""
            INSERT INTO auth.events
                (event_id, event_type, username, ip_address, user_agent,
                 success, timestamp, details)
            VALUES (:eid, :etype, :user, :ip, :ua, :success, :ts, :details)
            ON CONFLICT (event_id) DO NOTHING
        """), {
            "eid":     event["event_id"],
            "etype":   event["event_type"],
            "user":    event.get("username"),
            "ip":      event.get("ip_address"),
            "ua":      event.get("user_agent", ""),
            "success": event.get("success"),
            "ts":      event["timestamp"],
            "details": json.dumps(event.get("details", {})),
        })
        await session.commit()
    except Exception as e:
        log.exception("Failed to persist event: %s", e)
        await session.rollback()


async def consume_auth_events():
    consumer = AIOKafkaConsumer(
        TOPIC_EVENTS,
        bootstrap_servers=KAFKA_BROKER,
        group_id="event-persister-auth",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    log.info("Consuming %s ...", TOPIC_EVENTS)
    try:
        async for msg in consumer:
            async with SessionLocal() as session:
                await persist_auth_event(session, msg.value)
                log.info("Persisted %s for %s",
                         msg.value.get("event_type"),
                         msg.value.get("username"))
    finally:
        await consumer.stop()


# -----------------------------------------------------------------------------
# Persister security.alerts
# -----------------------------------------------------------------------------
async def persist_alert(session: AsyncSession, alert: dict):
    try:
        await session.execute(text("""
            INSERT INTO security.alerts
                (alert_id, timestamp, username, ip_address,
                 alert_type, severity, score, details)
            VALUES (:aid, :ts, :user, :ip, :atype, :sev, :score, :details)
            ON CONFLICT (alert_id) DO NOTHING
        """), {
            "aid":     alert["alert_id"],
            "ts":      alert["timestamp"],
            "user":    alert.get("username"),
            "ip":      alert.get("ip_address"),
            "atype":   alert["alert_type"],
            "sev":     alert.get("severity", "medium"),
            "score":   alert.get("score"),
            "details": json.dumps(alert.get("details", {})),
        })
        await session.commit()
    except Exception as e:
        log.exception("Failed to persist alert: %s", e)
        await session.rollback()


async def consume_alerts():
    consumer = AIOKafkaConsumer(
        TOPIC_ALERTS,
        bootstrap_servers=KAFKA_BROKER,
        group_id="event-persister-alerts",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    await consumer.start()
    log.info("Consuming %s ...", TOPIC_ALERTS)
    try:
        async for msg in consumer:
            async with SessionLocal() as session:
                await persist_alert(session, msg.value)
                log.info("Persisted alert %s", msg.value.get("alert_type"))
    finally:
        await consumer.stop()


# -----------------------------------------------------------------------------
# Main : 2 consumers parallèles
# -----------------------------------------------------------------------------
async def main():
    log.info("=" * 60)
    log.info("Event Persister starting (2 topics in parallel)")
    log.info("=" * 60)
    await asyncio.gather(
        consume_auth_events(),
        consume_alerts(),
    )


if __name__ == "__main__":
    asyncio.run(main())
