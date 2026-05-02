CREATE SCHEMA IF NOT EXISTS keycloak;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS tickets;
CREATE SCHEMA IF NOT EXISTS security;

-- =============================================================================
-- auth.events : SOURCE DE VERITE des événements d'auth
-- Alimentée UNIQUEMENT par event-persister qui consume Kafka.
-- Aucune app n'écrit ici directement — tout passe par Kafka.
-- =============================================================================
CREATE TABLE IF NOT EXISTS auth.events (
    id            BIGSERIAL PRIMARY KEY,
    event_id      UUID UNIQUE NOT NULL,
    event_type    VARCHAR(50) NOT NULL,
    username      VARCHAR(100),
    ip_address    VARCHAR(45),
    user_agent    TEXT,
    success       BOOLEAN,
    timestamp     TIMESTAMPTZ NOT NULL,
    details       JSONB,
    received_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_user ON auth.events(username);
CREATE INDEX IF NOT EXISTS idx_events_time ON auth.events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON auth.events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_ip   ON auth.events(ip_address);

-- =============================================================================
-- auth.users : référentiel local (synchronisé avec Keycloak via API admin)
-- =============================================================================
CREATE TABLE IF NOT EXISTS auth.users (
    id             SERIAL PRIMARY KEY,
    keycloak_id    VARCHAR(255) UNIQUE NOT NULL,
    username       VARCHAR(100) NOT NULL,
    email          VARCHAR(255),
    is_blocked     BOOLEAN DEFAULT FALSE,
    blocked_at     TIMESTAMPTZ,
    blocked_reason TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO auth.users (keycloak_id, username, email) VALUES
    ('demo-alice',   'alice',   'alice@pfe.local'),
    ('demo-bob',     'bob',     'bob@pfe.local'),
    ('demo-charlie', 'charlie', 'charlie@pfe.local')
ON CONFLICT (keycloak_id) DO NOTHING;

-- =============================================================================
-- tickets : application métier
-- =============================================================================
CREATE TABLE IF NOT EXISTS tickets.tickets (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT,
    priority    VARCHAR(20) DEFAULT 'medium',
    status      VARCHAR(20) DEFAULT 'open',
    created_by  VARCHAR(255) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets.comments (
    id         SERIAL PRIMARY KEY,
    ticket_id  INTEGER REFERENCES tickets.tickets(id) ON DELETE CASCADE,
    author     VARCHAR(100) NOT NULL,
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- security.alerts : alertes générées par le ML
-- Persistées par event-persister depuis le topic security.alerts
-- =============================================================================
CREATE TABLE IF NOT EXISTS security.alerts (
    id          BIGSERIAL PRIMARY KEY,
    alert_id    UUID UNIQUE NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL,
    username    VARCHAR(100),
    ip_address  VARCHAR(45),
    alert_type  VARCHAR(50) NOT NULL,
    severity    VARCHAR(20) DEFAULT 'medium',
    score       FLOAT,
    details     JSONB,
    is_resolved BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_alerts_time ON security.alerts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON security.alerts(alert_type);
