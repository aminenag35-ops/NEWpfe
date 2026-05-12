# Guide de déploiement - Projet PFE SSO + Kafka + ML

## 📋 Prérequis (Ubuntu Server)

```bash
sudo apt update && sudo apt upgrade -y

# Docker + Compose
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# Se déconnecter / reconnecter pour que le groupe prenne effet

# Vérifier
docker --version
docker compose version
```

**Configuration réseau :** ouvre les ports si tu accèdes depuis Windows :

```bash
sudo ufw allow 8080/tcp     # Keycloak
sudo ufw allow 5001/tcp     # Admin app
sudo ufw allow 5002/tcp     # Tickets
sudo ufw allow 5003/tcp     # Dashboard
sudo ufw allow 9092/tcp     # Kafka (optionnel)
```

Note l'IP de ton Ubuntu Server : `ip a | grep inet`. Disons que c'est `192.168.1.50`.

---

## 🚀 Étape 1 : Builder le JAR Keycloak (une seule fois)

```bash
cd ~/sso-project/keycloak-kafka-listener
chmod +x build.sh
./build.sh
```

Ça lance un conteneur Maven qui produit `build/keycloak-kafka-listener.jar`. Ce JAR sera monté automatiquement dans Keycloak via le volume défini dans `docker-compose.yml`.

---

## 🚀 Étape 2 : Lancer toute la stack

```bash
cd ~/sso-project
docker compose up -d
```

Vérifier que tout est OK (au bout de ~1-2 minutes) :

```bash
docker compose ps
docker compose logs -f keycloak       # Vérifie que le SPI Kafka est chargé
docker compose logs -f kafka_consumer # Doit dire "Connecté à Kafka"
```

Tu dois voir dans les logs Keycloak :
```
[KafkaEventListener] Producer initialisé -> kafka:9092 topic=keycloak-events
```

---

## 🚀 Étape 3 : Importer le realm Keycloak

1. Ouvre dans ton navigateur Windows : `http://192.168.1.50:8080`
2. Connecte-toi : **admin / admin**
3. En haut à gauche, ouvre le menu déroulant des realms → **Create Realm**
4. Clique sur **Browse...** et sélectionne `keycloak-realm-export.json` (depuis ton Windows tu peux l'envoyer par scp)
5. Clique **Create**

Le realm `sso-demo` est créé avec :
- 3 clients (admin-app, ticket-app, dashboard-app)
- 3 rôles (admin, user, support)
- 4 utilisateurs : `alice / bob / charlie / superadmin` (mots de passe dans le JSON)
- L'event listener `kafka` activé

**Vérifie que le listener est bien actif** : Realm Settings → Events → onglet **Config** → "Event Listeners" doit contenir `kafka`. Si non, ajoute-le.

---

## 🚀 Étape 4 : Tester le SSO

Depuis ton **Windows**, dans le navigateur :

| App         | URL                            | Login                          |
|-------------|--------------------------------|--------------------------------|
| Admin       | `http://192.168.1.50:5001`     | superadmin / Admin2024!        |
| Tickets     | `http://192.168.1.50:5002`     | alice / Alice2024!             |
| Dashboard   | `http://192.168.1.50:5003`     | superadmin / Admin2024!        |

⚠️ **Important** : pour que les redirections SSO marchent, depuis Windows utilise le **même nom d'hôte ou IP** que celui configuré dans les redirectUris. Si tu utilises l'IP `192.168.1.50` au lieu de `localhost`, mets à jour les redirectUris dans Keycloak :
- Realm `sso-demo` → Clients → chaque client → **Valid redirect URIs** → remplacer `localhost` par `192.168.1.50`.

Plus simple : ajoute dans `C:\Windows\System32\drivers\etc\hosts` (en admin) :
```
192.168.1.50    localhost
```
(ou utilise un nom dédié comme `sso.local`).

---

## 🚀 Étape 5 : Vérifier que les events arrivent dans Kafka

```bash
# Sur Ubuntu
docker exec -it sso_kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic keycloak-events --from-beginning
```

Connecte-toi à une app dans le navigateur → tu dois voir des JSON s'afficher dans ce terminal.

---

## 🚀 Étape 6 : Vérifier la base PostgreSQL

```bash
docker exec -it sso_postgres psql -U postgres -d logsdb

# Dans psql :
SELECT event_time, event_type, username, ip_address, error
FROM auth_events ORDER BY event_time DESC LIMIT 20;
```

Tu dois voir tes événements de login.

---

## 🚀 Étape 7 : Lancer les attaques depuis Windows

Sur Windows, installe Python 3 puis :

```cmd
cd attack-scripts
pip install -r requirements.txt

REM 1) D'abord, génère du trafic LÉGITIME (laisse tourner 5 min en parallèle)
python normal_traffic.py http://192.168.1.50:8080 5

REM 2) Brute force sur alice
python brute_force.py http://192.168.1.50:8080 alice

REM 3) Credential stuffing (IPs simulées via X-Forwarded-For)
python credential_stuffing.py http://192.168.1.50:8080

REM 4) Password spraying
python password_spraying.py http://192.168.1.50:8080 "Password123!"
```

Pendant ce temps, **garde le dashboard ouvert** sur `http://192.168.1.50:5003/dashboard` : tu verras les compteurs grimper, les top IPs apparaître, etc.

---

## 🚀 Étape 8 : Entraîner et lancer le modèle ML

Sur Ubuntu :

```bash
cd ~/sso-project/ml-detector
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure la connexion DB
export DB_HOST=localhost
export DB_USER=postgres
export DB_PASSWORD=postgres
export DB_NAME=logsdb

# 1) Entraîner (sur les données accumulées)
python detector.py train

# 2) Tester une détection one-shot
python detector.py detect

# 3) Lancer la boucle continue (en arrière-plan)
nohup python run_loop.py > ml.log 2>&1 &
```

Les alertes apparaissent dans le dashboard (section "Alertes ML") au bout de quelques secondes.

---

## 🛠️ Commandes utiles

```bash
# Tout arrêter
docker compose down

# Tout arrêter ET supprimer les données
docker compose down -v

# Logs d'un service en particulier
docker compose logs -f keycloak

# Re-builder une app après modif
docker compose up -d --build admin_app

# Reset complet
docker compose down -v && docker compose up -d
```

---

## 🐛 Problèmes courants

**"redirect_uri does not match"** → mets à jour les Valid Redirect URIs dans Keycloak (Clients → chaque client) avec ton IP réelle ou utilise le hosts file Windows pour mapper `localhost`.

**Le consumer Kafka boucle sur "Kafka pas prêt"** → Kafka peut prendre 30-60s à démarrer. Patience. Si ça persiste : `docker compose logs kafka`.

**Le SPI Kafka n'est pas chargé dans Keycloak** → vérifie que `keycloak-kafka-listener/build/*.jar` existe avant de lancer `docker compose up`. Sinon : `cd keycloak-kafka-listener && ./build.sh && cd .. && docker compose restart keycloak`.

**Pas de données dans `auth_events`** → vérifie successivement : 
1. Les logs du producer Keycloak (`docker compose logs keycloak | grep Kafka`)
2. Le topic existe (`docker exec sso_kafka kafka-topics --bootstrap-server kafka:9092 --list`)
3. Le consumer tourne (`docker compose logs kafka_consumer`)

**Le ML dit "Pas assez de données"** → génère plus de trafic d'abord (`normal_traffic.py` + attaques).
