"""
simulateur_trafic.py
====================

Génère du trafic synthétique vers l'App 2 (Tickets) pour faire vivre le pipeline
de détection.

Mode d'envoi : on POST des événements à `http://<app2>/api/event` qui les
publie sur Kafka. C'est plus simple et plus réaliste que de pousser
directement sur Kafka — on simule le résultat d'une vraie action utilisateur.

Scénarios :
    1. Trafic normal      : 3 employés, ~30 connexions chacun aux heures
                            de bureau (8h-18h locales).
    2. Brute force        : 50 tentatives échouées en 2 minutes pour
                            charlie depuis une IP suspecte.
    3. Horaire suspect    : connexion réussie de bob à 3h00 du matin.
    4. Vol de session     : alice se connecte avec succès depuis 5 IP
                            différentes en moins de 10 minutes.

Usage :
    python simulateur_trafic.py [--target http://localhost:5002]
                                [--scenario all|normal|brute|night|multi-ip]
"""

import argparse
import random
import time
from datetime import datetime, timezone, timedelta

import requests


DEFAULT_TARGET = "http://localhost:5002"


# -----------------------------------------------------------------------------
# Helper : envoyer un événement au backend
# -----------------------------------------------------------------------------

def send_event(target, event_type, username, ip, success, details=None):
    """Envoie un événement à l'App 2. Le timestamp sera ajouté côté serveur."""
    payload = {
        "event_type": event_type,
        "username": username,
        "ip_address": ip,
        "success": success,
        "details": details or {},
    }
    try:
        r = requests.post(f"{target}/api/event", json=payload, timeout=2)
        if r.status_code != 202:
            print(f"  [WARN] HTTP {r.status_code}: {r.text}")
    except requests.RequestException as e:
        print(f"  [ERROR] {e}")


# -----------------------------------------------------------------------------
# Scénario 1 — Trafic normal
# -----------------------------------------------------------------------------

NORMAL_USERS = [
    ("alice",   "192.168.1.10"),
    ("bob",     "192.168.1.11"),
    ("charlie", "192.168.1.12"),
]


def scenario_normal(target):
    """Trafic d'employés : ~30 connexions / user / journée, heures de bureau."""
    print("\n=== Scénario 1 : trafic normal ===")
    count = 0
    for username, ip in NORMAL_USERS:
        for _ in range(30):
            send_event(target, "login_success", username, ip, success=True)
            count += 1
            time.sleep(0.05)   # 50 ms entre événements
    print(f"  -> {count} événements normaux envoyés")


# -----------------------------------------------------------------------------
# Scénario 2 — Brute force
# -----------------------------------------------------------------------------

def scenario_brute_force(target):
    """50 logins échoués sur charlie depuis 10.0.0.99, en ~2 minutes."""
    print("\n=== Scénario 2 : brute force sur 'charlie' ===")
    attacker_ip = "10.0.0.99"
    target_user = "charlie"
    for i in range(50):
        send_event(
            target, "login_failed", target_user, attacker_ip,
            success=False, details={"attempt": i + 1}
        )
        # 50 tentatives en 2 minutes ≈ une toutes les 2.4 secondes
        time.sleep(2.4)
    # 51ème : login réussi (l'attaque a peut-être marché)
    send_event(target, "login_success", target_user, attacker_ip, success=True)
    print(f"  -> 50 échecs + 1 succès depuis {attacker_ip}")


# -----------------------------------------------------------------------------
# Scénario 3 — Horaire suspect
# -----------------------------------------------------------------------------

def scenario_unusual_hour(target):
    """
    On simule une connexion de bob à 3h du matin.
    Comme on ne peut pas remonter le temps, on triche sur le timestamp via le
    champ details — mais le ML détecte l'heure de l'événement reçu, donc on
    envoie en réel et la règle se déclenchera si on lance la simu de nuit.

    Pour un PFE, le plus propre est d'expliquer cela en démo : "à 3h du matin,
    le ML déclenche l'alerte unusual_hour automatiquement."
    """
    print("\n=== Scénario 3 : horaire suspect (bob) ===")
    # Astuce : on injecte 3 logins sous un user fictif "bob_night" pour ne pas
    # polluer le scénario brute force, et on note dans les détails.
    ip = "192.168.1.11"
    for _ in range(3):
        send_event(target, "login_success", "bob", ip, success=True,
                   details={"note": "simulated 3am login"})
        time.sleep(1)
    print("  -> Le détecteur déclenchera 'unusual_hour' si l'heure courante "
          "est en dehors des heures de bureau.")


# -----------------------------------------------------------------------------
# Scénario 4 — Multi-IP (vol de session)
# -----------------------------------------------------------------------------

def scenario_multi_ip(target):
    """alice se connecte depuis 5 IPs différentes en 10 min."""
    print("\n=== Scénario 4 : alice connectée depuis 5 IP en 10 min ===")
    suspicious_ips = [
        "203.0.113.10",
        "198.51.100.22",
        "185.100.87.33",
        "45.33.32.156",
        "91.240.118.11",
    ]
    for ip in suspicious_ips:
        send_event(target, "login_success", "alice", ip, success=True,
                   details={"note": "session theft scenario"})
        time.sleep(60)        # 1 minute entre chaque IP -> 5 IPs en 5 min
    print(f"  -> 5 connexions depuis 5 IPs distinctes")


# -----------------------------------------------------------------------------
# Entrée
# -----------------------------------------------------------------------------

SCENARIOS = {
    "normal":  scenario_normal,
    "brute":   scenario_brute_force,
    "night":   scenario_unusual_hour,
    "multi-ip": scenario_multi_ip,
}


def main():
    parser = argparse.ArgumentParser(description="Simulateur de trafic PFE")
    parser.add_argument("--target", default=DEFAULT_TARGET,
                        help="URL de l'App 2 (Tickets)")
    parser.add_argument("--scenario", default="all",
                        choices=["all"] + list(SCENARIOS.keys()))
    args = parser.parse_args()

    print("=" * 60)
    print("  Simulateur de trafic — PFE DevSecOps")
    print(f"  Cible : {args.target}")
    print("=" * 60)

    if args.scenario == "all":
        scenario_normal(args.target)
        scenario_brute_force(args.target)
        scenario_unusual_hour(args.target)
        scenario_multi_ip(args.target)
    else:
        SCENARIOS[args.scenario](args.target)

    print("\n" + "=" * 60)
    print("  Simulation terminée. Vérifiez le dashboard sur :5003")
    print("=" * 60)


if __name__ == "__main__":
    main()
