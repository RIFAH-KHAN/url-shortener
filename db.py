import os

import psycopg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/shortener",
)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def init_db():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                short_code VARCHAR(10) PRIMARY KEY,
                long_url   TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                expires_at TIMESTAMPTZ
            )
            """
        )
        # purani table me column na ho to add kar do
        conn.execute(
            "ALTER TABLE urls ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS clicks (
                id         BIGSERIAL PRIMARY KEY,
                short_code VARCHAR(10) NOT NULL REFERENCES urls(short_code),
                clicked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                user_agent TEXT,
                referer    TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_clicks_code ON clicks (short_code)"
        )