"""
Export d'un dataset LABELLISÉ pour évaluation du modèle.
=========================================================
Pour un mémoire de PFE, c'est essentiel : tu compares les prédictions
du modèle avec la vérité terrain (attaque oui/non) pour calculer
precision, recall, F1, ROC-AUC.

Approche : on définit des fenêtres temporelles "attaque" (à remplir
manuellement après tes sessions d'attaque) et on labellise les events
en fonction.

Usage :
    1. Édite la liste ATTACK_WINDOWS ci-dessous avec tes vrais horodatages
    2. python export_labeled_dataset.py
    3. Récupère dataset.csv -> à analyser dans un notebook Jupyter
"""
import os
import pandas as pd
from datetime import datetime
import psycopg2

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PWD  = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "logsdb")

# ==========================================================
# À REMPLIR MANUELLEMENT après tes sessions d'attaque
# Format : (début, fin, type_attaque, ip_source_si_connue)
# Mets None pour ip_source si tu ne sais pas / plusieurs IPs
# ==========================================================
ATTACK_WINDOWS = [
    # Exemple :
    # ("2025-01-15 14:30:00", "2025-01-15 14:35:00", "brute_force",       "192.168.1.42"),
    # ("2025-01-15 14:40:00", "2025-01-15 14:50:00", "credential_stuffing", None),
    # ("2025-01-15 14:55:00", "2025-01-15 15:00:00", "password_spraying", "192.168.1.42"),
]


def fetch_events():
    conn = psycopg2.connect(host=DB_HOST, user=DB_USER, password=DB_PWD, dbname=DB_NAME)
    df = pd.read_sql("""
        SELECT event_time, event_type, ip_address, username, user_agent, error, country
        FROM auth_events
        WHERE ip_address IS NOT NULL
        ORDER BY event_time
    """, conn)
    conn.close()
    return df


def label_events(df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute is_attack et attack_type."""
    df["is_attack"]   = False
    df["attack_type"] = None

    for start, end, atype, ip in ATTACK_WINDOWS:
        start = pd.to_datetime(start)
        end   = pd.to_datetime(end)
        mask = (df["event_time"] >= start) & (df["event_time"] <= end)
        if ip:
            mask &= (df["ip_address"] == ip)
        df.loc[mask, "is_attack"]   = True
        df.loc[mask, "attack_type"] = atype
    return df


def aggregate_per_ip(df: pd.DataFrame, window: str = "5min") -> pd.DataFrame:
    """Agrège par IP sur des fenêtres glissantes (granularité 'window')."""
    df["bucket"] = df["event_time"].dt.floor(window)
    df["is_failure"] = df["event_type"].str.contains("ERROR", na=False) | df["error"].notna()

    agg = df.groupby(["bucket", "ip_address"]).agg(
        n_events       = ("event_type", "count"),
        n_failures     = ("is_failure", "sum"),
        n_distinct_users = ("username", "nunique"),
        n_distinct_agents= ("user_agent", "nunique"),
        is_attack      = ("is_attack", "any"),       # True si au moins 1 event labellisé
    ).reset_index()
    agg["fail_ratio"] = agg["n_failures"] / agg["n_events"]
    return agg


def main():
    if not ATTACK_WINDOWS:
        print("⚠️  ATTACK_WINDOWS est vide. Édite ce fichier pour ajouter tes")
        print("   sessions d'attaque (timestamps), puis relance.")
        print("   Sans labels, pas d'évaluation supervisée possible.\n")

    df = fetch_events()
    print(f"[+] {len(df)} événements récupérés")

    df = label_events(df)
    n_attacks = df["is_attack"].sum()
    print(f"[+] {n_attacks} events labellisés comme attaque ({n_attacks/len(df)*100:.1f}%)")

    # Export brut event-level
    df.to_csv("dataset_events.csv", index=False)
    print(f"[+] dataset_events.csv -> {len(df)} lignes")

    # Export agrégé IP × fenêtre (pour entraîner le modèle)
    agg = aggregate_per_ip(df)
    agg.to_csv("dataset_features.csv", index=False)
    print(f"[+] dataset_features.csv -> {len(agg)} lignes (IP × bucket 5min)")
    print(f"    dont {agg['is_attack'].sum()} buckets d'attaque")


if __name__ == "__main__":
    main()
