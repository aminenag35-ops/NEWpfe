-- ============================================================
-- Application Ticketing – Schéma de base de données
-- ============================================================

\connect ticketing_db;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    keycloak_id     VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) NOT NULL,
    email           VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tickets (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    priority        VARCHAR(20) DEFAULT 'medium',
    status          VARCHAR(20) DEFAULT 'open',
    created_by      VARCHAR(255) NOT NULL,
    created_by_name VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ticket_history (
    id          SERIAL PRIMARY KEY,
    ticket_id   INTEGER REFERENCES tickets(id) ON DELETE CASCADE,
    status      VARCHAR(20) NOT NULL,
    changed_by  VARCHAR(100) NOT NULL,
    changed_at  TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_user ON tickets(created_by);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
