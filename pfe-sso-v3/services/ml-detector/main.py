"""
ML Detector v3 — async, publie alertes sur Kafka
=================================================

Différence vs v2 :
    - 100% async (aiokafka)
    - N'écrit plus directement en DB : il PUBLIE sur security.alerts,
      c'est event-persister qui matérialise en base.
    - Garde le blocage Redis direct (action immédiate, pas via Kafka)

Architecture :
    Kafka auth.events --> [règles + IsolationForest] --> Kafka security.alerts
                                                     --> Redis SETEX
"""
import asyncio
import json
import logging
import os
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
import redis.asyncio as redis


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s | %(message)s")
log = logging.getLogger("ml-detector")


# Config
KAFKA_BROKER = os.environ.get("KAFKA_BROKER", "kafka:9092")
TOPIC_EVENTS = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "security.alerts")
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

BRUTE_FORCE_THRESHOLD = int(os.environ.get("BRUTE_FORCE_THRESHOLD", 10))
BRUTE_FORCE_WINDOW = int(os.environ.get("BRUTE_FORCE_WINDOW", 120))
MULTI_IP_THRESHOLD = int(os.environ.get("MULTI_IP_THRESHOLD", 5))
MULTI_IP_WINDOW = int(os.environ.get("MULTI_IP_WINDOW", 600))
ENUM_THRESHOLD = int(os.environ.get("ENUM_THRESHOLD", 15))
ENUM_WINDOW = int(os.environ.get("ENUM_WINDOW", 300))
UNUSUAL_HOUR_START = int(os.environ.get("UNUSUAL_HOUR_START", 22))
UNUSUAL_HOUR_END = int(os.environ.get("UNUSUAL_HOUR_END", 6))
ML_RETRAIN_EVERY = 200
ML_WINDOW_SIZE = 1000
BLOCK_TTL = 3600


# -----------------------------------------------------------------------------
# Fenêtre glissante pour les règles
# -----------------------------------------------------------------------------
class SlidingWindow:
    """Maintient deux index : par username ET par IP."""
    def __init__(self):
        self._by_user = defaultdict(lambda: deque(maxlen=200))
        self._by_ip   = defaultdict(lambda: deque(maxlen=200))

    def add(self, event):
        if event.get("username"):
            self._by_user[event["username"]].append(event)
        if event.get("ip_address"):
            self._by_ip[event["ip_address"]].append(event)

    def recent_by_user(self, username, seconds):
        now = datetime.now(timezone.utc)
        return [e for e in self._by_user[username]
                if (now - e["_dt"]).total_seconds() <= seconds]

    def recent_by_ip(self, ip, seconds):
        now = datetime.now(timezone.utc)
        return [e for e in self._by_ip[ip]
                if (now - e["_dt"]).total_seconds() <= seconds]


# -----------------------------------------------------------------------------
# Règles déterministes
# -----------------------------------------------------------------------------
def detect_brute_force(window, event):
    if event.get("event_type") != "login_failed":
        return None
    failures = [e for e in window.recent_by_user(event["username"], BRUTE_FORCE_WINDOW)
                if e.get("event_type") == "login_failed"]
    if len(failures) >= BRUTE_FORCE_THRESHOLD:
        return {
            "alert_type": "brute_force", "severity": "high",
            "score": min(1.0, len(failures) / BRUTE_FORCE_THRESHOLD / 2),
            "details": {"failures_count": len(failures),
                        "window_seconds": BRUTE_FORCE_WINDOW},
        }
    return None


def detect_account_enumeration(window, event):
    """
    Détecte une seule IP qui essaie de nombreux usernames différents :
    signe d'un attaquant qui devine des comptes existants.
    """
    if event.get("event_type") != "login_failed":
        return None
    ip = event.get("ip_address")
    if not ip:
        return None
    recent = window.recent_by_ip(ip, ENUM_WINDOW)
    distinct_users = {e["username"] for e in recent
                      if e.get("event_type") == "login_failed" and e.get("username")}
    if len(distinct_users) >= ENUM_THRESHOLD:
        return {
            "alert_type": "account_enumeration", "severity": "high",
            "score": min(1.0, len(distinct_users) / ENUM_THRESHOLD / 2),
            "details": {
                "distinct_usernames": len(distinct_users),
                "samples": list(distinct_users)[:5],
                "window_seconds": ENUM_WINDOW,
            },
        }
    return None


def detect_unusual_hour(event):
    if event.get("event_type") != "login_success":
        return None
    hour_local = (event["_dt"].hour + 1) % 24  # UTC+1 Tunisie
    if hour_local >= UNUSUAL_HOUR_START or hour_local < UNUSUAL_HOUR_END:
        return {
            "alert_type": "unusual_hour", "severity": "medium",
            "score": 0.7, "details": {"hour_local": hour_local},
        }
    return None


def detect_multi_ip(window, event):
    if event.get("event_type") != "login_success":
        return None
    recent = window.recent_by_user(event["username"], MULTI_IP_WINDOW)
    distinct = {e["ip_address"] for e in recent if e.get("ip_address")}
    if len(distinct) >= MULTI_IP_THRESHOLD:
        return {
            "alert_type": "multi_ip", "severity": "critical",
            "score": min(1.0, len(distinct) / MULTI_IP_THRESHOLD / 2),
            "details": {"distinct_ips": list(distinct),
                        "window_seconds": MULTI_IP_WINDOW},
        }
    return None


# -----------------------------------------------------------------------------
# Modèle ML — IsolationForest sur fenêtre glissante
# -----------------------------------------------------------------------------
class MLAnomalyDetector:
    def __init__(self):
        self.model = None
        self.events_buffer = deque(maxlen=ML_WINDOW_SIZE)
        self.event_count_since_train = 0

    def _featurize(self, event):
        try:
            ip_octet = int(event["ip_address"].split(".")[0])
        except (ValueError, AttributeError, IndexError):
            ip_octet = 0
        return [
            event["_dt"].hour,
            1 if event.get("event_type") == "login_failed" else 0,
            ip_octet,
        ]

    def add_and_score(self, event):
        self.events_buffer.append(event)
        self.event_count_since_train += 1
        if len(self.events_buffer) < 50:
            return None
        if self.event_count_since_train >= ML_RETRAIN_EVERY or self.model is None:
            self._retrain()
            self.event_count_since_train = 0
        if self.model is None:
            return None
        score = -self.model.decision_function([self._featurize(event)])[0]
        return float(score)

    def _retrain(self):
        from sklearn.ensemble import IsolationForest
        log.info("ML retraining on %d events", len(self.events_buffer))
        X = [self._featurize(e) for e in self.events_buffer]
        self.model = IsolationForest(n_estimators=50, contamination=0.1,
                                      random_state=42, n_jobs=-1)
        self.model.fit(X)


# -----------------------------------------------------------------------------
# Émission d'une alerte (Kafka + Redis)
# -----------------------------------------------------------------------------
async def emit_alert(producer, redis_client, event, rule):
    alert = {
        "alert_id":   str(uuid.uuid4()),
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        "username":   event.get("username"),
        "ip_address": event.get("ip_address"),
        **rule,
    }
    log.warning("ALERT type=%s user=%s ip=%s score=%.2f",
                alert["alert_type"], alert["username"],
                alert["ip_address"], alert["score"])

    # 1. Publier sur Kafka (event-persister va matérialiser en DB)
    await producer.send_and_wait(TOPIC_ALERTS, value=alert)

    # 2. Bloquer l'IP dans Redis si sévérité élevée
    if alert["severity"] in ("high", "critical") and alert["ip_address"]:
        await redis_client.setex(
            f"blocked_ip:{alert['ip_address']}",
            BLOCK_TTL,
            alert["alert_type"],
        )


# -----------------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------------
async def main():
    log.info("=" * 60)
    log.info("ML Detector v3 starting")
    log.info("=" * 60)

    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BROKER,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        acks="all",
    )
    consumer = AIOKafkaConsumer(
        TOPIC_EVENTS,
        bootstrap_servers=KAFKA_BROKER,
        group_id="ml-detector-v3",
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)

    await producer.start()
    await consumer.start()
    log.info("Listening on %s ...", TOPIC_EVENTS)

    window = SlidingWindow()
    ml = MLAnomalyDetector()

    try:
        async for msg in consumer:
            try:
                event = msg.value
                event["_dt"] = datetime.fromisoformat(
                    event["timestamp"].replace("Z", "+00:00")
                )
                window.add(event)

                for rule in (
                    detect_brute_force(window, event),
                    detect_account_enumeration(window, event),
                    detect_unusual_hour(event),
                    detect_multi_ip(window, event),
                ):
                    if rule:
                        await emit_alert(producer, redis_client, event, rule)

                # ML
                ml_score = ml.add_and_score(event)
                if ml_score is not None and ml_score > 0.6:
                    await emit_alert(producer, redis_client, event, {
                        "alert_type": "ml_anomaly", "severity": "low",
                        "score": ml_score,
                        "details": {"model": "isolation_forest"},
                    })

            except Exception as e:
                log.exception("Failed to process event: %s", e)
    finally:
        await consumer.stop()
        await producer.stop()
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
