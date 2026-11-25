import os

import psycopg

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/shortener",
)


def get_connection():
    return psycopg.connect(DATABASE_URL)


def init_db():       #for examle 
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS urls (
                short_code VARCHAR(10) PRIMARY KEY,
                long_url   TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )