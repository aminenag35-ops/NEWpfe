"""
Détecteur d'anomalies sur les logs d'authentification Keycloak.
==============================================================

Approche pédagogique en 2 modes :
  1) train  : entraîne un Isolation Forest sur les events historiques
  2) detect : analyse une fenêtre récente, calcule des features par IP,
              et écrit les anomalies dans la table ml_alerts.

Pour un PFE, Isolation Forest est un excellent baseline non supervisé :
- pas besoin de labels
- détecte naturellement les comportements rares (brute force, IPs nouvelles)
- explicable (on peut afficher les features)

Lancer :
  python detector.py train
  python detector.py detect    # (à mettre dans un cron toutes les minutes)
"""

import os
import sys
import json
import pickle
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from sklearn.ensemble import IsolationForest

# --- Config ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PWD  = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "logsdb")

MODEL_PATH = os.getenv("MODEL_PATH", "model.pkl")
WINDOW_MIN = int(os.getenv("WINDOW_MIN", "10"))   # fenêtre d'analyse
TRAIN_DAYS = int(os.getenv("TRAIN_DAYS", "7"))    # historique pour entraîner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ml")


def db():
    return psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PWD, dbname=DB_NAME)


# ==========================================================
# Feature engineering : on agrège par (ip_address, fenêtre).
# Chaque ligne = comportement d'une IP sur la fenêtre.
# ==========================================================
def build_features(conn, since: datetime) -> pd.DataFrame:
    """
    Récupère les events depuis 'since' et calcule des features par IP.
    Features choisies (simples mais efficaces pour brute force) :
      - n_events           : volume total
      - n_failures         : nombre d'échecs
      - n_success          : nombre de succès
      - fail_ratio         : ratio échecs / total
      - n_distinct_users   : nombre d'usernames différents tentés
      - avg_interval_sec   : intervalle moyen entre tentatives
      - n_distinct_agents  : nombre de user-agents différents
    """
    query = """
        SELECT event_time, event_type, ip_address, username, user_agent, error
        FROM auth_events
        WHERE event_time >= %s
          AND ip_address IS NOT NULL
    """
    df = pd.read_sql(query, conn, params=(since,))
    if df.empty:
        return df

    df["is_failure"] = df["event_type"].str.contains("ERROR", na=False) | df["error"].notna()
    df["is_success"] = df["event_type"] == "LOGIN"

    rows = []
    for ip, g in df.groupby("ip_address"):
        g = g.sort_values("event_time")
        intervals = g["event_time"].diff().dt.total_seconds().dropna()
        rows.append({
            "ip_address":       ip,
            "n_events":         len(g),
            "n_failures":       int(g["is_failure"].sum()),
            "n_success":        int(g["is_success"].sum()),
            "fail_ratio":       g["is_failure"].mean(),
            "n_distinct_users": g["username"].nunique(),
            "avg_interval_sec": intervals.mean() if not intervals.empty else 0.0,
            "n_distinct_agents":g["user_agent"].nunique(),
        })
    return pd.DataFrame(rows)


FEATURE_COLS = [
    "n_events", "n_failures", "n_success", "fail_ratio",
    "n_distinct_users", "avg_interval_sec", "n_distinct_agents",
]


# ==========================================================
# Mode TRAIN
# ==========================================================
def train():
    conn = db()
    since = datetime.now() - timedelta(days=TRAIN_DAYS)
    log.info(f"Entraînement sur les events depuis {since}")

    df = build_features(conn, since)
    if df.empty or len(df) < 5:
        log.warning("Pas assez de données pour entraîner. Génère du trafic d'abord.")
        return

    X = df[FEATURE_COLS].fillna(0).values
    log.info(f"Dataset : {X.shape[0]} IPs, {X.shape[1]} features")

    # contamination = proportion attendue d'anomalies (à ajuster)
    model = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
    model.fit(X)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "features": FEATURE_COLS}, f)
    log.info(f"Modèle sauvegardé -> {MODEL_PATH}")


# ==========================================================
# Mode DETECT
# ==========================================================
def detect():
    if not os.path.exists(MODEL_PATH):
        log.error("Modèle absent. Lance d'abord : python detector.py train")
        return

    with open(MODEL_PATH, "rb") as f:
        bundle = pickle.load(f)
    model, features = bundle["model"], bundle["features"]

    conn = db()
    since = datetime.now() - timedelta(minutes=WINDOW_MIN)
    df = build_features(conn, since)
    if df.empty:
        log.info("Aucun événement dans la fenêtre.")
        return

    X = df[features].fillna(0).values
    df["score"]      = model.decision_function(X)   # plus c'est bas, plus c'est anormal
    df["is_anomaly"] = model.predict(X) == -1       # -1 = anomalie

    anomalies = df[df["is_anomaly"]]
    log.info(f"{len(anomalies)} IPs suspectes détectées sur {len(df)} analysées")

    # Insertion des alertes
    with conn.cursor() as cur:
        for _, row in anomalies.iterrows():
            reason = build_reason(row)
            cur.execute("""
                INSERT INTO ml_alerts (ip_address, username, score, is_anomaly, reason, features)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                row["ip_address"], None,
                float(row["score"]), True, reason,
                Json({f: float(row[f]) for f in features}),
            ))
    conn.commit()


def build_reason(row) -> str:
    """Génère une explication lisible pour l'alerte."""
    reasons = []
    if row["fail_ratio"] > 0.5 and row["n_failures"] >= 5:
        reasons.append(f"taux d'échec élevé ({row['fail_ratio']:.0%}, {row['n_failures']} échecs)")
    if row["n_distinct_users"] >= 5:
        reasons.append(f"{row['n_distinct_users']} usernames différents (credential stuffing ?)")
    if row["avg_interval_sec"] < 1.0 and row["n_events"] > 5:
        reasons.append(f"cadence très rapide ({row['avg_interval_sec']:.2f}s entre tentatives)")
    if row["n_events"] > 50:
        reasons.append(f"volume anormal : {row['n_events']} événements")
    return "; ".join(reasons) if reasons else "comportement statistique anormal"


# ==========================================================
# Entrée
# ==========================================================
if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("train", "detect"):
        print("Usage: python detector.py [train|detect]")
        sys.exit(1)
    {"train": train, "detect": detect}[sys.argv[1]]()
