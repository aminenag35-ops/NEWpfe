"""
simulateur_trafic.py
====================

Génère du trafic synthétique vers l'API Tickets pour faire vivre le pipeline.

Endpoint utilisé : POST /api/auth/failed (publique, ne nécessite pas de JWT).
                   POST /api/event-test  (debug, accepte tout type d'événement)

Pour les login_success simulés, on n'a pas de vrai JWT — on triche en utilisant
un endpoint /api/event-test qui accepte n'importe quel événement (dev only).

Scénarios :
    1. Trafic normal      : 30 connexions × 3 employés depuis IP de bureau
    2. Brute force        : 50 échecs sur charlie en 2 minutes
    3. Énumération        : 1 IP teste 20 usernames différents
    4. Multi-IP           : alice depuis 5 IPs en 5 minutes
    5. Horaire suspect    : login à minuit (basé sur heure courante)

Usage :
    python3 simulateur_trafic.py [--target http://localhost:8002] [--scenario all]
"""
import argparse
import random
import time
import requests


DEFAULT_TARGET = "http://localhost:8002"


def post_event(target, event_type, username, ip, success, details=None):
    """
    Envoie un événement vers l'API. Utilise /api/auth/failed pour login_failed
    (endpoint public) et /api/event-test pour le reste (endpoint dev).
    """
    if event_type == "login_failed":
        url = f"{target}/api/auth/failed"
        body = {"username": username, "details": details or {}}
    else:
        url = f"{target}/api/event-test"
        body = {
            "event_type": event_type,
            "username": username,
            "ip_address": ip,
            "success": success,
            "details": details or {},
        }
    try:
        r = requests.post(
            url, json=body, timeout=3,
            headers={"X-Forwarded-For": ip},  # on simule l'IP
        )
        if r.status_code >= 300:
            print(f"  [WARN] HTTP {r.status_code}: {r.text[:200]}")
    except requests.RequestException as e:
        print(f"  [ERROR] {e}")


# -----------------------------------------------------------------------------
# Scénario 1 : trafic normal (employés depuis le réseau interne)
# -----------------------------------------------------------------------------
def scenario_normal(target):
    print("\n=== Scénario 1 : trafic normal ===")
    employees = [("alice", "192.168.1.10"),
                 ("bob",   "192.168.1.11"),
                 ("charlie", "192.168.1.12")]
    count = 0
    for user, ip in employees:
        for _ in range(30):
            post_event(target, "login_success", user, ip, success=True)
            count += 1
            time.sleep(0.05)
    print(f"  -> {count} login_success envoyés depuis le réseau interne")


# -----------------------------------------------------------------------------
# Scénario 2 : brute force sur un utilisateur
# -----------------------------------------------------------------------------
def scenario_brute_force(target):
    print("\n=== Scénario 2 : brute force sur charlie ===")
    attacker_ip = "10.0.0.99"
    target_user = "charlie"
    for i in range(50):
        post_event(target, "login_failed", target_user, attacker_ip,
                   success=False, details={"attempt": i + 1})
        time.sleep(2.4)        # ~50 essais en 120 secondes
    print(f"  -> 50 login_failed depuis {attacker_ip} sur {target_user}")
    print(f"     Attendu : alerte brute_force (severity=high)")


# -----------------------------------------------------------------------------
# Scénario 3 : énumération de comptes (1 IP, beaucoup d'usernames)
# -----------------------------------------------------------------------------
def scenario_account_enumeration(target):
    print("\n=== Scénario 3 : énumération de comptes ===")
    attacker_ip = "203.0.113.42"
    # Liste de 20 prénoms communs - simule un attaquant qui devine les comptes
    candidates = ["admin", "root", "test", "user", "guest", "support",
                  "alice", "bob", "charlie", "david", "emma", "frank",
                  "grace", "henry", "iris", "jack", "karen", "louis",
                  "mary", "nathan"]
    for username in candidates:
        post_event(target, "login_failed", username, attacker_ip,
                   success=False, details={"enum_attempt": True})
        time.sleep(8)          # 20 users en ~160s, dans la fenêtre 5min
    print(f"  -> 20 usernames testés depuis {attacker_ip}")
    print(f"     Attendu : alerte account_enumeration (severity=high)")


# -----------------------------------------------------------------------------
# Scénario 4 : vol de session (1 user, plusieurs IPs)
# -----------------------------------------------------------------------------
def scenario_multi_ip(target):
    print("\n=== Scénario 4 : alice depuis 5 IPs en 5 minutes ===")
    suspicious_ips = [
        "203.0.113.10",   # USA (apparent)
        "198.51.100.22",  # autre USA
        "185.100.87.33",  # Pays-Bas
        "45.33.32.156",   # USA
        "91.240.118.11",  # Russie (apparent)
    ]
    for ip in suspicious_ips:
        post_event(target, "login_success", "alice", ip, success=True,
                   details={"note": "session theft scenario"})
        time.sleep(60)         # 1 min entre chaque
    print(f"  -> 5 login_success de alice depuis 5 pays différents")
    print(f"     Attendu : alerte multi_ip (severity=critical)")


# -----------------------------------------------------------------------------
# Scénario 5 : horaire suspect (le ML évalue l'heure courante UTC+1)
# -----------------------------------------------------------------------------
def scenario_unusual_hour(target):
    print("\n=== Scénario 5 : horaire suspect ===")
    print("  Note : se déclenche si l'heure locale est entre 22h et 6h.")
    print("         Pour tester en journée, modifiez UNUSUAL_HOUR_START/END")
    print("         dans docker-compose.yml")
    for _ in range(3):
        post_event(target, "login_success", "bob", "192.168.1.11", True,
                   details={"note": "off-hours login"})
        time.sleep(2)
    print("  -> 3 login_success envoyés")


SCENARIOS = {
    "normal": scenario_normal,
    "brute":  scenario_brute_force,
    "enum":   scenario_account_enumeration,
    "multiip": scenario_multi_ip,
    "night":  scenario_unusual_hour,
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--target", default=DEFAULT_TARGET,
                   help="URL de l'API Tickets (défaut: http://localhost:8002)")
    p.add_argument("--scenario", default="all",
                   choices=["all"] + list(SCENARIOS.keys()))
    args = p.parse_args()

    print("=" * 60)
    print("  Simulateur de trafic — PFE DevSecOps v3")
    print(f"  Cible : {args.target}")
    print("=" * 60)

    if args.scenario == "all":
        for fn in SCENARIOS.values():
            fn(args.target)
    else:
        SCENARIOS[args.scenario](args.target)

    print("\n" + "=" * 60)
    print("  Terminé. Vérifiez le dashboard sur :3003")
    print("=" * 60)


if __name__ == "__main__":
    main()
