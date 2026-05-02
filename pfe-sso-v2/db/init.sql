-- =============================================================================
-- Initialisation de la base pfe_db
-- Une seule base, plusieurs schémas pour isoler les domaines
-- =============================================================================

-- Schéma pour Keycloak (il créera ses propres tables au premier démarrage)
CREATE SCHEMA IF NOT EXISTS keycloak;

-- Schéma "auth" : utilisateurs locaux + audit
CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id           SERIAL PRIMARY KEY,
    keycloak_id  VARCHAR(255) UNIQUE NOT NULL,
    username     VARCHAR(100) NOT NULL,
    email        VARCHAR(255),
    is_blocked   BOOLEAN DEFAULT FALSE,
    blocked_at   TIMESTAMP,
    blocked_reason TEXT,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auth.audit_log (
    id           BIGSERIAL PRIMARY KEY,
    timestamp    TIMESTAMP DEFAULT NOW(),
    username     VARCHAR(100),
    action       VARCHAR(100) NOT NULL,
    ip_address   VARCHAR(45),
    success      BOOLEAN DEFAULT TRUE,
    details      JSONB
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON auth.audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_time ON auth.audit_log(timestamp);

-- Schéma "tickets" : application métier
CREATE SCHEMA IF NOT EXISTS tickets;

CREATE TABLE IF NOT EXISTS tickets.tickets (
    id           SERIAL PRIMARY KEY,
    title        VARCHAR(255) NOT NULL,
    description  TEXT,
    priority     VARCHAR(20) DEFAULT 'medium',
    status       VARCHAR(20) DEFAULT 'open',
    created_by   VARCHAR(255) NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets.comments (
    id           SERIAL PRIMARY KEY,
    ticket_id    INTEGER REFERENCES tickets.tickets(id) ON DELETE CASCADE,
    author       VARCHAR(100) NOT NULL,
    content      TEXT NOT NULL,
    created_at   TIMESTAMP DEFAULT NOW()
);

-- Schéma "security" : alertes générées par le ML
CREATE SCHEMA IF NOT EXISTS security;

CREATE TABLE IF NOT EXISTS security.alerts (
    id           BIGSERIAL PRIMARY KEY,
    timestamp    TIMESTAMP DEFAULT NOW(),
    username     VARCHAR(100),
    ip_address   VARCHAR(45),
    alert_type   VARCHAR(50) NOT NULL,        -- brute_force, unusual_hour, multi_ip, ml_anomaly
    severity     VARCHAR(20) DEFAULT 'medium',-- low, medium, high, critical
    score        FLOAT,
    details      JSONB,
    is_resolved  BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON security.alerts(timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON security.alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_user ON security.alerts(username);

-- Quelques utilisateurs de démo pour tester l'admin (les vrais sont dans Keycloak)
INSERT INTO auth.users (keycloak_id, username, email) VALUES
    ('demo-alice',   'alice',   'alice@pfe.local'),
    ('demo-bob',     'bob',     'bob@pfe.local'),
    ('demo-charlie', 'charlie', 'charlie@pfe.local')
ON CONFLICT (keycloak_id) DO NOTHING;
