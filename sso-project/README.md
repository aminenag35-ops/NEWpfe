# Projet PFE — SSO Keycloak + Kafka + Postgres + Détection IA

Architecture complète pour un système SSO multi-applications avec pipeline
de logs vers Kafka, stockage Postgres, et détection d'anomalies par ML
(Isolation Forest).

## 🏗️ Architecture

```
                            ┌─────────────────────────────────┐
                            │  Trafic légitime + attaques     │
                            │  (depuis Windows)               │
                            └──────────────┬──────────────────┘
                                           ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ App 1    │   │ App 2    │   │ App 3    │
   │ Admin    │   │ Tickets  │   │ Dashboard│
   │ :5001    │   │ :5002    │   │ :5003    │
   └────┬─────┘   └────┬─────┘   └────┬─────┘
        │              │              │
        └──────────────┴──────────────┘
                       │ OIDC SSO
                       ▼
              ┌─────────────────┐         ┌─────────────────┐
              │   KEYCLOAK      │ ───────▶│   KAFKA         │
              │   :8080         │  events │   topic:        │
              │  (+ SPI custom) │         │ keycloak-events │
              └────────┬────────┘         └────────┬────────┘
                       │                           │
                       ▼                           ▼
              ┌─────────────────┐         ┌─────────────────┐
              │   POSTGRES      │         │ Kafka Consumer  │
              │  - keycloak     │◀────────│  enrichit +     │
              │  - ticketsdb    │         │  insère         │
              │  - logsdb       │         └─────────────────┘
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  ML Detector    │
              │  Isolation      │
              │  Forest         │
              └─────────────────┘
```

## 📦 Composants

| Dossier                         | Rôle |
|---------------------------------|------|
| `docker-compose.yml`            | Orchestration de toute la stack |
| `keycloak-realm-export.json`    | Config Keycloak (realm, clients, users, rôles) |
| `keycloak-kafka-listener/`      | SPI Java : Keycloak → Kafka |
| `kafka-consumer/`               | Consumer Python : Kafka → Postgres |
| `ml-detector/`                  | Détection d'anomalies (Isolation Forest) |
| `apps/admin-app/`               | App 1 — gestion utilisateurs |
| `apps/ticket-app/`              | App 2 — tickets et profil |
| `apps/dashboard-app/`           | App 3 — dashboard sécurité temps réel |
| `attack-scripts/`               | Scripts d'attaque (à lancer depuis Windows) |
| `sql/init.sql`                  | Init des bases Postgres |
| `docs/DEPLOY.md`                | **Guide pas à pas** |

## 🚀 Démarrage rapide

```bash
# 1. Builder le SPI Keycloak (1 fois)
cd keycloak-kafka-listener && ./build.sh && cd ..

# 2. Lancer la stack
docker compose up -d

# 3. Importer le realm via l'UI Keycloak (http://<ip>:8080)
#    Login admin/admin → Create Realm → upload keycloak-realm-export.json

# 4. Tester le SSO
#    http://<ip>:5001 (admin)
#    http://<ip>:5002 (tickets)
#    http://<ip>:5003 (dashboard)
```

Voir [docs/DEPLOY.md](docs/DEPLOY.md) pour le guide complet.

## 🧪 Comptes de test

| Username       | Password         | Rôles          |
|----------------|------------------|----------------|
| superadmin     | Admin2024!       | admin, user    |
| alice          | Alice2024!       | user           |
| bob            | Bob2024!         | user           |
| charlie        | Charlie2024!     | user, support  |

## 🔥 Attaques simulées

L'approche retenue combine **scripts custom (labellisation propre)** + **outils pros (réalisme)** + **validation externe (rigueur)**.

### Scripts Python rapides
```bash
# Trafic normal (à lancer en parallèle pour avoir une baseline)
python attack-scripts/normal_traffic.py http://<ip>:8080 60

# Brute force / stuffing / spraying
python attack-scripts/brute_force.py http://<ip>:8080 alice
python attack-scripts/credential_stuffing.py http://<ip>:8080
python attack-scripts/password_spraying.py http://<ip>:8080 Password123!
```

### Hydra (outil de référence pentest) — voir `attack-scripts/hydra/README.md`
```bash
cd attack-scripts/hydra
./run_hydra_bruteforce.sh 192.168.1.50 alice
./run_hydra_spraying.sh 192.168.1.50 "Password123!"
```

### Burp Suite Intruder (le plus visuel pour la soutenance) — voir `attack-scripts/burp/README.md`
Démo en live ultra impressionnante avec tableau temps réel des tentatives.

## 🤖 ML

```bash
cd ml-detector
python detector.py train     # entraînement
python detector.py detect    # détection one-shot
python run_loop.py           # boucle continue (à mettre en service systemd)
```

## 📊 Validation académique externe (CICIDS2017)

Pour donner une dimension scientifique à ton mémoire, le projet inclut une étape de **validation externe** sur le dataset public CICIDS2017 (référence en détection d'intrusion).

```bash
# 1. Évaluation interne sur Keycloak
cd ml-detector && python evaluate.py
# -> keycloak_results.json

# 2. Téléchargement CICIDS2017 (gratuit après formulaire)
#    https://www.unb.ca/cic/datasets/ids-2017.html
#    -> place Tuesday-WorkingHours.pcap_ISCX.csv dans ml-detector/cicids/

# 3. Validation externe
cd cicids && python validate_on_cicids.py
# -> cicids_results.json + roc_curve.png

# 4. Tableau comparatif (avec code LaTeX prêt à coller)
python compare_results.py
```

Voir `ml-detector/cicids/README.md` pour le guide détaillé et les phrases types pour ton mémoire.

## 📅 Workflow recommandé

`docs/WORKFLOW.md` te donne un planning sur 2 semaines avec l'enchaînement complet : setup → génération de trafic → ML → évaluation → rédaction.

## 🔒 Notes pour un PFE

- **Code volontairement simple et lisible** : pas de magie, pas de framework lourd côté apps.
- **Pour la prod** il faudrait : vérification cryptographique des JWT (python-jose + JWKS), HTTPS partout, rotation des secrets, batching côté consumer Kafka, vrai GeoIP (MaxMind), retraining périodique du modèle.
- **Labellisation des attaques** : à chaque session d'attaque, note l'horodatage de début/fin. Tu peux ainsi construire un dataset labellisé pour évaluer ton modèle (precision/recall/F1) en plus de l'approche non-supervisée.
