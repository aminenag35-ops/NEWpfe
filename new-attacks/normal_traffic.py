"""
Trafic LÉGITIME simulé
=======================
Simule des utilisateurs normaux qui se connectent puis se déconnectent.
Indispensable pour entraîner le modèle ML : sans baseline normale,
le modèle ne sait pas distinguer le bruit des attaques.

Lance ça AVANT les scripts d'attaque (ou en parallèle) :
    python normal_traffic.py http://<ip-ubuntu>:8080
"""
import sys, time, random, requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
DURATION_MIN = int(sys.argv[2]) if len(sys.argv) > 2 else 5

REALM         = "sso-demo"
CLIENT_ID     = "ticket-app"
CLIENT_SECRET = "ticket-app-secret"

# Comptes valides à créer dans Keycloak (cf guide)
USERS = [
    ("alice",   "Alice2024!"),
    ("bob",     "Bob2024!"),
    ("charlie", "Charlie2024!"),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebKit/537.36 Chrome/120.0"


def login(user, pwd):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type":   "password",
        "client_id":    CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "username":     user,
        "password":     pwd,
    }
    r = requests.post(url, data=data, headers={"User-Agent": UA}, timeout=5)
    return r.status_code == 200


print(f"[*] Trafic légitime pendant {DURATION_MIN} minutes")
print(f"[*] Cible : {KEYCLOAK_URL}\n")

end = time.time() + DURATION_MIN * 60
n = 0
while time.time() < end:
    user, pwd = random.choice(USERS)
    ok = login(user, pwd)
    n += 1
    print(f"  [{n}] {user} -> {'✓' if ok else '✗'}")
    # Cadence humaine : entre 5 et 30 secondes entre logins
    time.sleep(random.uniform(5, 30))

print(f"\n[*] {n} connexions simulées.")
