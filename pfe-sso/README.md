# PFE – SSO DevSecOps avec Keycloak (Phase 1)

## Architecture

```
┌─────────────┐     OIDC      ┌──────────────┐
│  Navigateur │◄─────────────►│   Keycloak   │
│             │               │  (IdP:8080)  │
└──┬──┬──┬────┘               └──────┬───────┘
   │  │  │                           │
   │  │  │    ┌──────────────────────┘
   │  │  │    │  User Federation (LDAP)
   │  │  │    ▼
   │  │  │  ┌──────────┐
   │  │  │  │  LLDAP   │
   │  │  │  │ (3890)   │
   │  │  │  └──────────┘
   │  │  │
   │  │  └──► App IAM        (localhost:5001)
   │  └─────► App Ticketing  (localhost:5002)
   └────────► App Audit      (localhost:5003)
                    │
                    ▼
              ┌──────────┐
              │PostgreSQL│
              │ (5432)   │
              └──────────┘
```

## Démarrage rapide

```bash
# 1. Lancer toute l'infrastructure
docker-compose up --build -d

# 2. Attendre que Keycloak soit prêt (~30-60 secondes)
docker-compose logs -f keycloak  # Attendre "Running the server"

# 3. Vérifier les services
# - Keycloak :     http://localhost:8080  (admin / admin)
# - LLDAP :        http://localhost:17170 (admin / admin_password)
# - App IAM :      http://localhost:5001
# - App Ticketing: http://localhost:5002
# - App Audit :    http://localhost:5003
```

## Utilisateurs de test

| Utilisateur | Mot de passe | Rôle    | Accès                                    |
|-------------|-------------|---------|------------------------------------------|
| alice       | password    | admin   | Tout (IAM, Ticketing, Audit, logs, users)|
| bob         | password    | manager | IAM (users), Ticketing (gestion), Audit  |
| charlie     | password    | user    | IAM (profil), Ticketing (ses tickets)    |

## ÉTAPE 8 – Scénario de démonstration pour le jury

### Scénario 1 : SSO – Connexion unique

1. Ouvrir http://localhost:5001 (IAM)
2. Vous êtes redirigé vers Keycloak → Se connecter avec **alice / password**
3. Vous êtes redirigé vers l'IAM, connecté automatiquement
4. Cliquer sur **Ticketing** dans la barre de navigation
5. **✅ Vous êtes connecté automatiquement** (SSO fonctionne !)
6. Cliquer sur **Audit** → connecté automatiquement aussi

### Scénario 2 : Contrôle d'accès par rôle

**Avec alice (admin) :**
1. Sur IAM → accès à : Profil ✅, Liste Utilisateurs ✅, Journal d'Audit ✅
2. Sur Ticketing → voit tous les tickets, peut changer les statuts ✅
3. Sur Audit → voit tous les logs, filtres disponibles ✅

**Avec charlie (user) :**
1. Se déconnecter → se reconnecter avec charlie / password
2. Sur IAM → Profil ✅, Liste Utilisateurs 🔒 (403), Journal d'Audit 🔒 (403)
3. Sur Ticketing → voit uniquement ses tickets, ne peut pas changer les statuts
4. Sur Audit → dashboard basique, pas d'accès aux logs détaillés 🔒

### Scénario 3 : Traçabilité

1. Se connecter avec alice
2. Naviguer dans les 3 applications
3. Aller sur Audit → Logs → voir toutes les actions enregistrées
4. Filtrer par utilisateur "alice" → les actions sont tracées
5. Filtrer par date du jour → les actions récentes apparaissent

### Scénario 4 : Ticketing complet

1. Se connecter avec charlie (user)
2. Créer un ticket : titre "Problème VPN", priorité Haute
3. Le ticket apparaît avec statut "Ouvert"
4. Se déconnecter → se connecter avec bob (manager)
5. Le ticket de charlie est visible
6. Changer le statut en "En cours" → l'historique est mis à jour
7. Changer en "Fermé"

### Scénario 5 : Déconnexion SSO

1. Cliquer sur "Déconnexion" depuis n'importe quelle app
2. Vous êtes redirigé vers Keycloak → session terminée
3. Accéder à une autre app → vous devez vous reconnecter

## Arrêter l'infrastructure

```bash
docker-compose down          # Arrêter (données conservées)
docker-compose down -v       # Arrêter + supprimer les données
```

## Structure du projet

```
pfe-sso/
├── docker-compose.yml          # Infrastructure complète
├── keycloak/
│   └── realm-export.json       # Configuration realm + clients + users
├── shared/
│   ├── oidc.py                 # Middleware OIDC commun
│   ├── database.py             # Helper PostgreSQL
│   └── templates/
│       └── base.html           # Template HTML de base
├── apps/
│   ├── iam/                    # Application IAM (port 5001)
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── templates/
│   ├── ticketing/              # Application Ticketing (port 5002)
│   │   ├── app.py
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── templates/
│   └── audit/                  # Application Audit (port 5003)
│       ├── app.py
│       ├── Dockerfile
│       ├── requirements.txt
│       └── templates/
└── db/
    ├── init-databases.sql      # Création des 3 BDD
    ├── iam.sql                 # Schéma IAM
    ├── ticketing.sql           # Schéma Ticketing
    └── audit.sql               # Schéma Audit
```
