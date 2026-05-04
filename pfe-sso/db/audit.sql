-- ============================================================
-- Application Audit & Traçabilité – Schéma de base de données
-- ============================================================

\connect audit_db;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    keycloak_id     VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) NOT NULL,
    email           VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS action_logs (
    id          SERIAL PRIMARY KEY,
    keycloak_id VARCHAR(255) NOT NULL,
    username    VARCHAR(100) NOT NULL,
    action      VARCHAR(100) NOT NULL,
    details     TEXT DEFAULT '',
    timestamp   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_logs_user ON action_logs(username);
CREATE INDEX IF NOT EXISTS idx_logs_time ON action_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_action ON action_logs(action);
