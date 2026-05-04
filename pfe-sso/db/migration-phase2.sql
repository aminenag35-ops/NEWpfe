-- ============================================================
-- PHASE 2 – Migration SQL
-- Enrichissement des tables existantes + création anomaly_db
-- ============================================================

-- ============================================================
-- 1) Enrichir la table audit_log dans iam_db
-- ============================================================
\c iam_db;

ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS user_agent VARCHAR(512);
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS hour_of_day INTEGER;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS session_id VARCHAR(128);

-- Index pour les requêtes d'analyse
CREATE INDEX IF NOT EXISTS idx_audit_log_hour ON audit_log(hour_of_day);
CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);

-- ============================================================
-- 2) Enrichir la table ticket_history dans ticketing_db
-- ============================================================
\c ticketing_db;

ALTER TABLE ticket_history ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE ticket_history ADD COLUMN IF NOT EXISTS user_agent VARCHAR(512);
ALTER TABLE ticket_history ADD COLUMN IF NOT EXISTS hour_of_day INTEGER;
ALTER TABLE ticket_history ADD COLUMN IF NOT EXISTS session_id VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_ticket_history_hour ON ticket_history(hour_of_day);
CREATE INDEX IF NOT EXISTS idx_ticket_history_changed_by ON ticket_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_ticket_history_changed_at ON ticket_history(changed_at);

-- ============================================================
-- 3) Enrichir la table action_logs dans audit_db
-- ============================================================
\c audit_db;

ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS user_agent VARCHAR(512);
ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS hour_of_day INTEGER;
ALTER TABLE action_logs ADD COLUMN IF NOT EXISTS session_id VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_action_logs_hour ON action_logs(hour_of_day);
CREATE INDEX IF NOT EXISTS idx_action_logs_username ON action_logs(username);
CREATE INDEX IF NOT EXISTS idx_action_logs_timestamp ON action_logs(timestamp);

-- ============================================================
-- 4) Créer la base anomaly_db et ses tables
-- ============================================================
-- Note: la base anomaly_db est créée dans init-databases-phase2.sql
-- Ici on crée les tables (à exécuter après la création de la base)

\c anomaly_db;

CREATE TABLE IF NOT EXISTS anomalies (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    username VARCHAR(128) NOT NULL,
    keycloak_id VARCHAR(256),
    anomaly_score FLOAT NOT NULL,
    anomaly_type VARCHAR(64) NOT NULL,
    model_used VARCHAR(64) NOT NULL,
    details JSONB,
    is_confirmed BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp ON anomalies(timestamp);
CREATE INDEX IF NOT EXISTS idx_anomalies_username ON anomalies(username);
CREATE INDEX IF NOT EXISTS idx_anomalies_score ON anomalies(anomaly_score);
CREATE INDEX IF NOT EXISTS idx_anomalies_type ON anomalies(anomaly_type);

CREATE TABLE IF NOT EXISTS model_metrics (
    id SERIAL PRIMARY KEY,
    model_name VARCHAR(64) NOT NULL,
    accuracy FLOAT,
    precision_score FLOAT,
    recall FLOAT,
    f1_score FLOAT,
    trained_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_metrics_name ON model_metrics(model_name);
CREATE INDEX IF NOT EXISTS idx_model_metrics_trained_at ON model_metrics(trained_at);
