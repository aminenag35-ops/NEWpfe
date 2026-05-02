"""
simulateur_trafic_reel.py
==========================

Génère du VRAI trafic d'authentification en faisant des requêtes HTTP réelles
vers Keycloak. Pas de JSON inventé : Keycloak voit chaque requête, vérifie les
credentials, et GÉNÈRE LUI-MÊME les events qui partent dans Kafka via le
keycloak-bridge.

Pourquoi c'est mieux que la version v2 :
    - Les IPs sont les vraies IPs HTTP vues par Keycloak
    - Les usernames sont vraiment testés (pas juste loggés)
    - Les login_failed sont de vrais échecs (mauvais mot de passe)
    - Le pipeline est testé de bout en bout

Astuce IP : on utilise le header X-Forwarded-For pour simuler des IPs
différentes (Keycloak honore ce header s'il vient d'un reverse proxy de
confiance, ou en mode dev). Pour des IPs vraiment différentes en prod,
utilisez Tor ou un pool de proxies.

Usage :
    pip install requests
    python3 simulateur_trafic_reel.py --keycloak http://localhost:8080 --scenario brute
"""
import argparse
import random
import time
import uuid
from datetime import datetime
import requests


REALM = "pfe"
CLIENT_ID = "spa-tickets"
CLIENT_SECRET = None  # spa-tickets est public


def make_session(fake_ip=None, user_agent=None):
    """Crée une session HTTP avec headers spoofés pour simuler une IP/UA."""
    s = requests.Session()
    if fake_ip:
        s.headers["X-Forwarded-For"] = fake_ip
        s.headers["X-Real-IP"] = fake_ip
    if user_agent:
        s.headers["User-Agent"] = user_agent
    return s


def attempt_login(keycloak_url, username, password, fake_ip=None, user_agent=None):
    """
    Tente une vraie authentification via le endpoint OIDC de Keycloak.
    Retourne (success, status_code, error_msg).
    """
    url = f"{keycloak_url}/realms/{REALM}/protocol/openid-connect/token"
    s = make_session(fake_ip, user_agent)
    try:
        r = s.post(url, data={
            "grant_type": "password",
            "client_id":  CLIENT_ID,
            "username":   username,
            "password":   password,
            "scope":      "openid",
        }, timeout=5)
        if r.status_code == 200:
            return True, 200, None
        else:
            err = r.json().get("error_description", "auth failed")
            return False, r.status_code, err
    except requests.RequestException as e:
        return False, 0, str(e)


# =============================================================================
# SCENARIOS — chaque scénario génère de VRAIES requêtes Keycloak
# =============================================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/122.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) Safari/604.1",
]


def scenario_normal(kc_url):
    """30 connexions réussies pour 3 employés depuis IPs de bureau."""
    print("\n=== Scénario 1 : trafic NORMAL (vrais logins réussis) ===")
    employees = [
        ("alice",   "192.168.1.10"),
        ("bob",     "192.168.1.11"),
        ("charlie", "192.168.1.12"),
    ]
    success_count = 0
    for username, ip in employees:
        for i in range(10):
            ua = random.choice(USER_AGENTS)
            ok, status, _ = attempt_login(kc_url, username, "password", ip, ua)
            if ok:
                success_count += 1
            time.sleep(0.3)
    print(f"  -> {success_count}/30 logins réussis (vrais events Keycloak)")


def scenario_brute_force(kc_url):
    """50 vraies tentatives de login échouées sur charlie depuis une IP."""
    print("\n=== Scénario 2 : BRUTE FORCE réel sur charlie ===")
    print("    Keycloak verra 50 LOGIN_ERROR depuis 10.0.0.99")
    attacker_ip = "10.0.0.99"
    target_user = "charlie"
    wrong_passwords = [
        "123456", "password1", "qwerty", "letmein", "admin",
        "charlie123", "welcome", "monkey", "dragon", "master"
    ]
    failures = 0
    for i in range(50):
        pwd = random.choice(wrong_passwords) + str(random.randint(1, 99))
        ok, status, err = attempt_login(kc_url, target_user, pwd, attacker_ip,
                                          USER_AGENTS[0])
        if not ok:
            failures += 1
            if i % 10 == 0:
                print(f"    [{i+1}/50] échec: {err}")
        time.sleep(2.0)        # ~50 essais en 100 secondes
    print(f"  -> {failures}/50 échecs réels enregistrés par Keycloak")


def scenario_account_enumeration(kc_url):
    """Une IP teste 20 usernames différents avec mot de passe bidon."""
    print("\n=== Scénario 3 : ÉNUMÉRATION DE COMPTES ===")
    print("    Une IP teste 20 usernames pour deviner ceux qui existent")
    attacker_ip = "203.0.113.42"
    candidates = [
        "admin", "root", "test", "user", "guest", "support", "info",
        "alice", "bob", "charlie", "david", "emma", "frank", "grace",
        "henry", "iris", "jack", "karen", "louis", "mary"
    ]
    for username in candidates:
        ok, status, err = attempt_login(
            kc_url, username, "TryMe2024!",
            attacker_ip, USER_AGENTS[1]
        )
        marker = "OK" if ok else "X"
        print(f"    [{marker}] {username}: {err if not ok else 'login réussi'}")
        time.sleep(8)
    print(f"  -> 20 usernames testés depuis {attacker_ip}")


def scenario_multi_ip(kc_url):
    """alice se connecte depuis 5 IPs différentes (vol de session)."""
    print("\n=== Scénario 4 : MULTI-IP — alice depuis 5 pays apparents ===")
    suspicious_ips = [
        ("203.0.113.10",   "Mozilla/5.0 (Windows...) Chrome/120"),
        ("198.51.100.22",  "Mozilla/5.0 (Macintosh...) Safari"),
        ("185.100.87.33",  "Mozilla/5.0 (Linux...) Firefox"),
        ("45.33.32.156",   "Mozilla/5.0 (X11...) Chrome"),
        ("91.240.118.11",  "curl/8.4.0"),  # même celui-là est suspect
    ]
    for ip, ua in suspicious_ips:
        ok, status, err = attempt_login(kc_url, "alice", "password", ip, ua)
        print(f"    {ip} ({ua[:30]}...) -> {'OK' if ok else err}")
        time.sleep(45)         # 5 IPs en ~3 minutes
    print(f"  -> alice loguée depuis 5 IPs distinctes")


def scenario_unusual_hour(kc_url):
    """Login réussi depuis n'importe où (la règle teste l'heure courante)."""
    print("\n=== Scénario 5 : HORAIRE SUSPECT ===")
    print("    Note : se déclenche si l'heure locale est entre 22h et 6h")
    print("           Sinon, modifiez UNUSUAL_HOUR_* dans .env")
    for _ in range(3):
        ok, _, err = attempt_login(kc_url, "bob", "password",
                                    "192.168.1.11", USER_AGENTS[0])
        print(f"    bob -> {'OK' if ok else err}")
        time.sleep(2)


def scenario_credential_stuffing(kc_url):
    """
    Credential stuffing : mêmes paires login/password testées sur plusieurs comptes
    depuis plusieurs IPs (simulation d'une fuite de mots de passe).
    """
    print("\n=== Scénario 6 : CREDENTIAL STUFFING ===")
    print("    Une liste de credentials connus testée sur plusieurs comptes")
    leaked_creds = [
        ("alice",   "Password123"),
        ("alice",   "Welcome2024"),
        ("bob",     "Password123"),
        ("charlie", "Password123"),
        ("admin",   "admin123"),
    ]
    rotating_ips = ["198.51.100.5", "198.51.100.6", "198.51.100.7"]
    for username, password in leaked_creds:
        ip = random.choice(rotating_ips)
        ok, _, err = attempt_login(kc_url, username, password, ip, USER_AGENTS[2])
        print(f"    [{ip}] {username}/{password} -> {'OK' if ok else err}")
        time.sleep(3)


SCENARIOS = {
    "normal":    scenario_normal,
    "brute":     scenario_brute_force,
    "enum":      scenario_account_enumeration,
    "multiip":   scenario_multi_ip,
    "night":     scenario_unusual_hour,
    "stuffing":  scenario_credential_stuffing,
}


def main():
    p = argparse.ArgumentParser(description="Simulateur de trafic RÉEL Keycloak")
    p.add_argument("--keycloak", default="http://localhost:8080",
                   help="URL de Keycloak (défaut: http://localhost:8080)")
    p.add_argument("--scenario", default="all",
                   choices=["all"] + list(SCENARIOS.keys()))
    args = p.parse_args()

    print("=" * 65)
    print("  Simulateur de trafic RÉEL — PFE DevSecOps v3")
    print(f"  Keycloak : {args.keycloak}")
    print(f"  Realm    : {REALM}")
    print("=" * 65)
    print("\n  Toutes les requêtes sont de VRAIS appels HTTP à Keycloak.")
    print("  Keycloak génère lui-même les events qui sont publiés sur Kafka.\n")

    if args.scenario == "all":
        for fn in SCENARIOS.values():
            fn(args.keycloak)
    else:
        SCENARIOS[args.scenario](args.keycloak)

    print("\n" + "=" * 65)
    print("  Terminé. Les events vont apparaître dans Kafka dans ~5 secondes")
    print("  (poll interval du keycloak-bridge).")
    print("  Vérifiez : http://<IP>:3003 (dashboard temps réel)")
    print("=" * 65)


if __name__ == "__main__":
    main()
