-- ==========================================================
-- Initialisation des bases de données du projet
-- Crée 3 bases : keycloak, ticketsdb, logsdb
-- ==========================================================

-- Base pour Keycloak (gérée par Keycloak lui-même)
CREATE DATABASE keycloak;

-- Base pour l'app Tickets
CREATE DATABASE ticketsdb;

-- Base pour les logs et le ML
CREATE DATABASE logsdb;

-- ==========================================================
-- Tables de l'app Tickets
-- ==========================================================
\c ticketsdb;

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,         -- sub Keycloak
    username VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'open',     -- open / in_progress / closed
    priority VARCHAR(50) DEFAULT 'normal', -- low / normal / high
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS comments (
    id SERIAL PRIMARY KEY,
    ticket_id INT REFERENCES tickets(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    username VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ==========================================================
-- Tables de logs et résultats ML
-- ==========================================================
\c logsdb;

-- Table principale : tous les événements Keycloak captés via Kafka
CREATE TABLE IF NOT EXISTS auth_events (
    id BIGSERIAL PRIMARY KEY,
    event_time TIMESTAMP NOT NULL,
    event_type VARCHAR(100) NOT NULL,      -- LOGIN, LOGIN_ERROR, LOGOUT...
    realm_id VARCHAR(255),
    client_id VARCHAR(255),
    user_id VARCHAR(255),
    username VARCHAR(255),
    ip_address VARCHAR(64),
    user_agent TEXT,
    error VARCHAR(255),                    -- ex: invalid_user_credentials
    session_id VARCHAR(255),
    country VARCHAR(64),                   -- enrichi par le consumer
    raw_json JSONB,                        -- événement brut au cas où
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_events_time     ON auth_events(event_time);
CREATE INDEX idx_events_ip       ON auth_events(ip_address);
CREATE INDEX idx_events_user     ON auth_events(username);
CREATE INDEX idx_events_type     ON auth_events(event_type);

-- Table : résultats du modèle ML (alertes)
CREATE TABLE IF NOT EXISTS ml_alerts (
    id BIGSERIAL PRIMARY KEY,
    detected_at TIMESTAMP DEFAULT NOW(),
    ip_address VARCHAR(64),
    username VARCHAR(255),
    score FLOAT,                           -- score d'anomalie
    is_anomaly BOOLEAN,
    reason TEXT,                           -- explication lisible
    features JSONB                         -- features utilisées
);

CREATE INDEX idx_alerts_time ON ml_alerts(detected_at);
CREATE INDEX idx_alerts_ip   ON ml_alerts(ip_address);
