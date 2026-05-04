-- ============================================================
-- Application IAM – Schéma de base de données
-- ============================================================

\connect iam_db;

CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    keycloak_id     VARCHAR(255) UNIQUE NOT NULL,
    username        VARCHAR(100) NOT NULL,
    email           VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

-- Rôles par défaut
INSERT INTO roles (name, description) VALUES
    ('admin',   'Administrateur – accès total'),
    ('manager', 'Manager – accès intermédiaire'),
    ('user',    'Utilisateur standard')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    keycloak_id VARCHAR(255) NOT NULL,
    username    VARCHAR(100) NOT NULL,
    action      VARCHAR(100) NOT NULL,
    timestamp   TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
