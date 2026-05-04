"""
shared/database.py – Connexion PostgreSQL simple pour les 3 applications
"""

import os
import psycopg2
import psycopg2.extras


def get_db():
    """Retourne une connexion PostgreSQL."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    conn.autocommit = True
    return conn


def query(sql, params=None):
    """Exécute une requête SELECT et retourne les lignes en dicts."""
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


def execute(sql, params=None):
    """Exécute une requête INSERT/UPDATE/DELETE."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()
