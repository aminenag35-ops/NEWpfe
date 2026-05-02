# PFE DevSecOps — Phase 2 simplifiée

Architecture event-driven : 3 microservices Flask + Keycloak SSO + Kafka KRaft
+ ML temps réel + Redis + PostgreSQL.

## Démarrage

```bash
# 1. Lancer toute l'infra (sur Ubuntu Server avec Docker installé)
docker compose up --build -d

# 2. Attendre ~60s que Keycloak finisse d'importer le realm
docker compose logs -f keycloak  # attendre "Running the server"

# 3. Vérifier que le ML detector écoute Kafka
docker compose logs ml-detector

# 4. Injecter du trafic et des attaques
python3 simulateur_trafic.py --scenario all

# 5. Ouvrir le dashboard
firefox http://localhost:5003
```

## Services

| Service          | Port  | Rôle                                  |
|------------------|-------|---------------------------------------|
| Keycloak         | 8080  | SSO OIDC (admin/admin)                |
| App Admin        | 5001  | CRUD users, audit, blocage IP         |
| App Tickets      | 5002  | Génère les events vers Kafka          |
| App Dashboard    | 5003  | Visualise les alertes en WebSocket    |
| Kafka            | 9092  | Bus d'événements (mode KRaft)         |
| PostgreSQL       | 5432  | Persistence (schémas auth/tickets/security) |
| Redis            | 6379  | Cache des IPs bloquées (TTL 1h)       |

## Topics Kafka

- `auth.events`     : tous les événements d'authentification (App 2 → ML)
- `security.alerts` : alertes générées (ML → App 3 dashboard)

## Comptes Keycloak

| User    | Mot de passe | Rôle    |
|---------|--------------|---------|
| alice   | password     | admin   |
| bob     | password     | manager |
| charlie | password     | user    |

## Tester un scénario en isolation

```bash
python3 simulateur_trafic.py --scenario brute     # brute force
python3 simulateur_trafic.py --scenario night     # horaire suspect
python3 simulateur_trafic.py --scenario multi-ip  # vol session
python3 simulateur_trafic.py --scenario normal    # trafic propre
```

## Arrêt

```bash
docker compose down       # arrêter (données conservées)
docker compose down -v    # tout effacer
```
