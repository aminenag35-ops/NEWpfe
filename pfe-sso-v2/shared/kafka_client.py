"""
shared/kafka_client.py
----------------------
Wrappers simples autour de kafka-python pour produire / consommer des événements
au format JSON.

Pourquoi ce wrapper :
    kafka-python est un peu verbeux. Ici on cache la sérialisation JSON et la
    gestion d'erreurs basique pour que les apps utilisent une API à 2 lignes.

Format des événements (convention de projet) :
    {
        "event_type": "login_success" | "login_failed" | "ticket_created" ...,
        "username":   "alice",
        "ip_address": "192.168.1.10",
        "timestamp":  "2026-05-02T14:30:00Z",
        "details":    { ... }   # optionnel, libre
    }
"""

import json
import logging
import os
from datetime import datetime, timezone

from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError

log = logging.getLogger(__name__)


def get_producer():
    """
    Retourne un producteur Kafka prêt à l'emploi.
    Sérialise automatiquement les valeurs en JSON UTF-8.
    """
    broker = os.environ.get("KAFKA_BROKER", "kafka:9092")
    return KafkaProducer(
        bootstrap_servers=[broker],
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        # Petit batch pour avoir du quasi-temps réel sans massacrer le CPU
        linger_ms=20,
        retries=3,
        acks="all",
    )


def get_consumer(topic, group_id):
    """
    Retourne un consommateur Kafka attaché à un topic + un consumer group.
    Désérialise automatiquement le JSON.
    """
    broker = os.environ.get("KAFKA_BROKER", "kafka:9092")
    return KafkaConsumer(
        topic,
        bootstrap_servers=[broker],
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


def publish_event(producer, topic, event_type, username, ip_address,
                  success=True, details=None):
    """
    Publie un événement sur Kafka avec un format standard.

    On utilise `username` comme clé Kafka : tous les événements d'un même user
    iront dans la même partition, ce qui est utile pour la détection d'attaques
    par utilisateur (ordre garanti).
    """
    event = {
        "event_type": event_type,
        "username": username,
        "ip_address": ip_address,
        "success": success,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details or {},
    }
    try:
        producer.send(topic, key=username, value=event)
        # On ne flush() pas à chaque envoi pour la perf — KafkaProducer batch.
    except KafkaError as e:
        log.error("Kafka publish failed: %s", e)
