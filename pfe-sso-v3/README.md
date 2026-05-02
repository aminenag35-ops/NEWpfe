# PFE DevSecOps v3 — Détection ML sur VRAIS événements Keycloak

## 🎯 Différence majeure avec les versions précédentes

Avant : le simulateur **inventait** des événements JSON et les poussait dans Kafka.
**Maintenant** : Keycloak **génère lui-même** chaque événement à partir de vraies
requêtes HTTP. Le pipeline reçoit donc des données **authentiques** :
- Vraies IPs vues par Keycloak
- Vrais timestamps de logins
- Vrais codes d'erreur (`invalid_user_credentials`, `user_disabled`, etc.)
- Vrais user-agents
- Vrais `userId` Keycloak

## Architecture

```
1. User/Simulateur → POST HTTP vers Keycloak
2. Keycloak        → vérifie credentials, génère event LOGIN ou LOGIN_ERROR
3. keycloak-bridge → poll API Admin Keycloak toutes les 5s
4. keycloak-bridge → publie sur Kafka topic auth.events
5. ml-detector     → consume, applique règles + IsolationForest
6. event-persister → matérialise en PostgreSQL
7. Dashboard       → reçoit alertes en WebSocket
```

## Démarrage rapide

```bash
# 1. Configurer l'IP serveur
nano .env   # mettre SERVER_IP=192.168.1.50

# 2. Adapter le realm
SERVER_IP=$(grep SERVER_IP .env | cut -d= -f2)
sed -i "s|http://localhost:|http://${SERVER_IP}:|g" keycloak/realm-export.json

# 3. Lancer
docker compose up -d --build

# 4. Attendre Keycloak (~90s)
docker compose logs -f keycloak | grep "started in"

# 5. Vérifier le bridge
docker compose logs keycloak-bridge

# 6. Lancer une attaque RÉELLE
pip install requests
python3 simulateur_trafic_reel.py --keycloak http://localhost:8080 --scenario brute
```

## Vérifier les vrais events

### Via Keycloak Admin
1. `http://IP:8080/admin` (admin/admin)
2. Realm `pfe` → Events → Login events
3. Tous les login_success/error en temps réel

### Via Kafka UI
1. `http://IP:8090`
2. Topic `auth.events` → Messages
3. Chaque event a `"source": "keycloak_real"`

### Via logs
```bash
docker compose logs -f keycloak-bridge
```

Sortie attendue :
```
REAL login_failed | user=charlie ip=10.0.0.99
Published 50 real Keycloak events
```

## Les 6 scénarios d'attaques RÉELLES

| Scénario | Description | Attaque détectée |
|---|---|---|
| `normal` | 30 logins réussis | aucune |
| `brute` | 50 logins échoués sur charlie | brute_force |
| `enum` | 20 usernames testés | account_enumeration |
| `multiip` | alice depuis 5 IPs | multi_ip |
| `night` | login en heures suspectes | unusual_hour |
| `stuffing` | mêmes creds sur plusieurs comptes | brute_force/enum |

```bash
python3 simulateur_trafic_reel.py --scenario brute
python3 simulateur_trafic_reel.py --scenario all
```

## Note sur les IPs

Le simulateur envoie `X-Forwarded-For` mais Keycloak ignore ce header par défaut
(sécurité). Donc Keycloak voit l'IP du conteneur Docker source.

**Pour avoir des vraies IPs distinctes** :
1. Lancer le simulateur depuis plusieurs machines/VMs
2. Mettre Keycloak derrière nginx avec `KC_PROXY=edge`

Pour un PFE, expliquer cette limite est plus honnête que la cacher.

## Comptes de test

| Username | Password | Rôles |
|---|---|---|
| alice | password | admin, user |
| bob | password | manager, user |
| charlie | password | user |

## URLs

| Service | URL |
|---|---|
| Keycloak Admin | http://IP:8080/admin |
| Kafka UI | http://IP:8090 |
| App Tickets | http://IP:3002 |
| App Admin | http://IP:3001 |
| App Dashboard | http://IP:3003 |
| API Tickets docs | http://IP:8002/docs |

## Dépannage

**keycloak-bridge ne voit aucun event** :
```bash
# Vérifier dans Keycloak Admin que les events sont ON :
# Realm Settings → Events → "Save events" doit être ON
```

**Brute force déclenche blocage Keycloak** :
On a désactivé `bruteForceProtected: false` pour permettre les tests ML.
