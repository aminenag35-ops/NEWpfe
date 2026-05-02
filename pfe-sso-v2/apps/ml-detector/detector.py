"""
ML Detector — détection d'anomalies en temps réel
==================================================

Architecture choisie : RÈGLES + ML (hybride)
    Pour les attaques bien définies (brute-force, horaire suspect, multi-IP),
    des règles simples sont plus précises et explicables qu'un ML. On les
    applique d'abord. Pour les anomalies "qu'on ne sait pas nommer", on
    réentraîne périodiquement un Isolation Forest sur fenêtre glissante.

Flux :
    1. Consomme le topic `auth.events`.
    2. Pour chaque événement : applique les règles déterministes.
       Si une règle se déclenche -> publie sur `security.alerts` + écrit en DB
       + bloque l'IP dans Redis.
    3. Toutes les N événements : réentraîne IsolationForest et flagge
       les outliers de la fenêtre courante.

Pourquoi pas un modèle plus sophistiqué :
    Pour le scope de ce PFE, IsolationForest est suffisant et reste
    interprétable. Un autoencoder ou LSTM apporterait de la complexité sans
    bénéfice mesurable sur 4 scénarios définis.
"""

import os
import sys
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone

sys.path.insert(0, "/app/shared")

import psycopg2
import redis
from kafka_client import get_consumer, get_producer

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s | %(message)s"
)
log = logging.getLogger("ml-detector")


# -----------------------------------------------------------------------------
# Configuration (depuis l'environnement)
# -----------------------------------------------------------------------------

TOPIC_EVENTS = os.environ.get("KAFKA_TOPIC_EVENTS", "auth.events")
TOPIC_ALERTS = os.environ.get("KAFKA_TOPIC_ALERTS", "security.alerts")

BRUTE_FORCE_THRESHOLD = int(os.environ.get("BRUTE_FORCE_THRESHOLD", 10))
BRUTE_FORCE_WINDOW = int(os.environ.get("BRUTE_FORCE_WINDOW", 120))      # sec
MULTI_IP_THRESHOLD = int(os.environ.get("MULTI_IP_THRESHOLD", 5))
MULTI_IP_WINDOW = int(os.environ.get("MULTI_IP_WINDOW", 600))            # sec
UNUSUAL_HOUR_START = int(os.environ.get("UNUSUAL_HOUR_START", 22))
UNUSUAL_HOUR_END = int(os.environ.get("UNUSUAL_HOUR_END", 6))

ML_RETRAIN_EVERY = 200                 # réentraîne tous les N événements
ML_WINDOW_SIZE = 1000                  # garde les N derniers événements pour fit
BLOCK_TTL_SECONDS = 3600               # 1h de blocage par défaut


# -----------------------------------------------------------------------------
# État en mémoire (fenêtres glissantes par utilisateur)
# -----------------------------------------------------------------------------
# On garde par user un deque des derniers événements pour calculer les règles.
# Pour 100 users actifs, c'est trivial en mémoire.

class SlidingWindow:
    """Fenêtre glissante d'événements par utilisateur."""
    def __init__(self):
        self._events = defaultdict(lambda: deque(maxlen=200))

    def add(self, username, event):
        self._events[username].append(event)

    def recent(self, username, seconds):
        """Retourne les événements de l'user dans les N dernières secondes."""
        now = datetime.now(timezone.utc)
        return [
            e for e in self._events[username]
            if (now - e["_dt"]).total_seconds() <= seconds
        ]


# -----------------------------------------------------------------------------
# Règles de détection
# -----------------------------------------------------------------------------

def detect_brute_force(window, event):
    """
    Règle 1 : trop d'échecs de login pour un même utilisateur en peu de temps.
    """
    if event.get("event_type") != "login_failed":
        return None

    failures = [
        e for e in window.recent(event["username"], BRUTE_FORCE_WINDOW)
        if e.get("event_type") == "login_failed"
    ]
    if len(failures) >= BRUTE_FORCE_THRESHOLD:
        return {
            "alert_type": "brute_force",
            "severity": "high",
            "score": min(1.0, len(failures) / BRUTE_FORCE_THRESHOLD / 2),
            "details": {
                "failures_count": len(failures),
                "window_seconds": BRUTE_FORCE_WINDOW,
            }
        }
    return None


def detect_unusual_hour(event):
    """
    Règle 2 : connexion réussie pendant une plage horaire suspecte.
    Le timestamp de l'événement est en UTC ; on convertit grossièrement en
    heure locale (Tunisie = UTC+1).
    """
    if event.get("event_type") != "login_success":
        return None

    hour_utc = event["_dt"].hour
    hour_local = (hour_utc + 1) % 24   # ajustement Tunisie/Europe

    is_unusual = (
        hour_local >= UNUSUAL_HOUR_START or hour_local < UNUSUAL_HOUR_END
    )
    if is_unusual:
        return {
            "alert_type": "unusual_hour",
            "severity": "medium",
            "score": 0.7,
            "details": {"hour_local": hour_local}
        }
    return None


def detect_multi_ip(window, event):
    """
    Règle 3 : un même user se connecte depuis trop d'IP différentes en peu
    de temps (vol de session / VPN suspect).
    """
    if event.get("event_type") != "login_success":
        return None

    recent = window.recent(event["username"], MULTI_IP_WINDOW)
    distinct_ips = {e["ip_address"] for e in recent if e.get("ip_address")}

    if len(distinct_ips) >= MULTI_IP_THRESHOLD:
        return {
            "alert_type": "multi_ip",
            "severity": "critical",
            "score": min(1.0, len(distinct_ips) / MULTI_IP_THRESHOLD / 2),
            "details": {
                "distinct_ips": list(distinct_ips),
                "window_seconds": MULTI_IP_WINDOW,
            }
        }
    return None


# -----------------------------------------------------------------------------
# Modèle ML — Isolation Forest sur fenêtre glissante
# -----------------------------------------------------------------------------

class MLAnomalyDetector:
    """
    Réentraîne périodiquement un IsolationForest sur les features extraites
    de la fenêtre récente d'événements.

    Features par événement :
        - hour_of_day        : heure UTC
        - is_failed          : 1 si event_type == 'login_failed' sinon 0
        - ip_octet_1         : premier octet de l'IP (proxy de localisation)
    """

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
        """
        Ajoute l'événement à la fenêtre, réentraîne si besoin, et retourne un
        score d'anomalie pour cet événement (None si modèle pas encore prêt).
        """
        self.events_buffer.append(event)
        self.event_count_since_train += 1

        if len(self.events_buffer) < 50:
            return None  # pas assez de données pour entraîner

        if self.event_count_since_train >= ML_RETRAIN_EVERY or self.model is None:
            self._retrain()
            self.event_count_since_train = 0

        if self.model is None:
            return None

        features = [self._featurize(event)]
        # decision_function : plus c'est négatif, plus c'est anormal
        score = -self.model.decision_function(features)[0]
        return float(score)

    def _retrain(self):
        from sklearn.ensemble import IsolationForest
        log.info("ML retraining on %d events...", len(self.events_buffer))
        X = [self._featurize(e) for e in self.events_buffer]
        self.model = IsolationForest(
            n_estimators=50,
            contamination=0.1,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X)


# -----------------------------------------------------------------------------
# Sortie : DB + Kafka + Redis
# -----------------------------------------------------------------------------

def db_connect():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def redis_connect():
    return redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)


def emit_alert(producer, db_conn, r, event, alert):
    """
    Centralise les 3 effets de bord d'une alerte :
        1. Insertion en base (history)
        2. Publication Kafka (pour le dashboard)
        3. Blocage de l'IP dans Redis (pour les apps)
    """
    log.warning(
        "ALERT type=%s user=%s ip=%s score=%.2f",
        alert["alert_type"], event["username"],
        event["ip_address"], alert["score"]
    )

    # 1. DB
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO security.alerts "
            "(username, ip_address, alert_type, severity, score, details) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (
                event["username"],
                event["ip_address"],
                alert["alert_type"],
                alert["severity"],
                alert["score"],
                json.dumps(alert["details"]),
            )
        )
    db_conn.commit()

    # 2. Kafka (le dashboard est consommateur de ce topic)
    producer.send(TOPIC_ALERTS, value={
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "username": event["username"],
        "ip_address": event["ip_address"],
        **alert,
    })

    # 3. Redis : blocage avec TTL
    if alert["severity"] in ("high", "critical"):
        r.setex(f"blocked_ip:{event['ip_address']}",
                BLOCK_TTL_SECONDS,
                alert["alert_type"])


# -----------------------------------------------------------------------------
# Boucle principale
# -----------------------------------------------------------------------------

def main():
    log.info("=" * 60)
    log.info("ML Detector starting")
    log.info("=" * 60)

    consumer = get_consumer(TOPIC_EVENTS, group_id="ml-detector-v1")
    producer = get_producer()
    db_conn = db_connect()
    r = redis_connect()
    window = SlidingWindow()
    ml = MLAnomalyDetector()

    log.info("Listening on topic %s ...", TOPIC_EVENTS)

    for message in consumer:
        try:
            event = message.value
            # Parse le timestamp en datetime aware
            event["_dt"] = datetime.fromisoformat(
                event["timestamp"].replace("Z", "+00:00")
            )

            window.add(event["username"], event)

            # 1. Règles déterministes (rapides, explicables)
            for rule in (
                detect_brute_force(window, event),
                detect_unusual_hour(event),
                detect_multi_ip(window, event),
            ):
                if rule:
                    emit_alert(producer, db_conn, r, event, rule)

            # 2. ML (capte les anomalies "inconnues")
            ml_score = ml.add_and_score(event)
            if ml_score is not None and ml_score > 0.6:
                emit_alert(producer, db_conn, r, event, {
                    "alert_type": "ml_anomaly",
                    "severity": "low",
                    "score": ml_score,
                    "details": {"model": "isolation_forest"}
                })

        except Exception as e:
            log.exception("Failed to process event: %s", e)


if __name__ == "__main__":
    main()
