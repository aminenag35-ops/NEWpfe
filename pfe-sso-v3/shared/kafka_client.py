"""
shared/kafka_client.py
======================
Wrappers async autour de aiokafka.

Pourquoi async :
    Les API FastAPI sont async et veulent publier sur Kafka sans bloquer
    le thread. aiokafka est l'équivalent async de kafka-python.

Format des événements :
    {
        "event_id":   "uuid-v4",          # déduplication
        "event_type": "login_success" | ...,
        "username":   "alice",
        "ip_address": "10.0.0.1",
        "user_agent": "Mozilla/...",
        "success":    true,
        "timestamp":  "2026-05-02T14:30:00Z",
        "details":    { ... }
    }
"""
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

log = logging.getLogger(__name__)


class KafkaPublisher:
    """
    Producteur Kafka long-lived. Une instance par process.
    Lifecycle géré par lifespan FastAPI (start au démarrage, stop à l'arrêt).
    """

    def __init__(self):
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        broker = os.environ.get("KAFKA_BROKER", "kafka:9092")
        self._producer = AIOKafkaProducer(
            bootstrap_servers=broker,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            linger_ms=20,
            acks="all",
        )
        await self._producer.start()
        log.info("Kafka producer connected to %s", broker)

    async def stop(self):
        if self._producer:
            await self._producer.stop()

    async def publish_auth_event(
        self,
        topic: str,
        event_type: str,
        username: str,
        ip_address: str,
        success: bool = True,
        user_agent: str = "",
        details: Optional[dict] = None,
    ):
        """Publie un événement d'authentification au format standard du projet."""
        event = {
            "event_id":   str(uuid.uuid4()),
            "event_type": event_type,
            "username":   username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success":    success,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "details":    details or {},
        }
        await self._producer.send_and_wait(topic, key=username, value=event)
        return event


def make_consumer(topic: str, group_id: str) -> AIOKafkaConsumer:
    """Crée un consumer async non démarré (à start() dans le code appelant)."""
    broker = os.environ.get("KAFKA_BROKER", "kafka:9092")
    return AIOKafkaConsumer(
        topic,
        bootstrap_servers=broker,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
