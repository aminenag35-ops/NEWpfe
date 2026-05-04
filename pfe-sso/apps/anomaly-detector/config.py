import os
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = int(os.getenv("DB_PORT", 5432))
DB_USER = os.getenv("DB_USER", "pfe")
DB_PASSWORD = os.getenv("DB_PASSWORD", "pfe_secret")
DATABASES = {
    "iam_db": {"table":"audit_log","username_col":"username","timestamp_col":"timestamp","action_col":"action"},
    "audit_db": {"table":"action_logs","username_col":"username","timestamp_col":"timestamp","action_col":"action"},
    "ticketing_db": {"table":"ticket_history","username_col":"changed_by","timestamp_col":"changed_at","action_col":"status"},
}
ANOMALY_DB = "anomaly_db"
ANALYSIS_INTERVAL_SECONDS = int(os.getenv("ANALYSIS_INTERVAL", 300))
LOOKBACK_HOURS = int(os.getenv("LOOKBACK_HOURS", 24))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", 0.6))
MODEL_WEIGHTS = {"isolation_forest": 0.40, "one_class_svm": 0.30, "autoencoder": 0.30}
UNUSUAL_HOURS_START = 22
UNUSUAL_HOURS_END = 6
FEATURE_COLUMNS = ["hour_of_day","action_count_per_hour","unique_actions","error_403_count","avg_time_between_actions","ip_change_count","is_unusual_hour"]
