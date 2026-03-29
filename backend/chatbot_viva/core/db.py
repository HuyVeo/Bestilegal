"""PostgreSQL connection pool management."""

import atexit
import logging
from typing import Optional

from chatbot_viva.core import config
from chatbot_viva.core.singleton import singleton

logger = logging.getLogger(__name__)


@singleton
def get_db_pool():
    """Get or create the global connection pool (thread-safe singleton)."""
    from psycopg_pool import ConnectionPool

    logger.info("Initializing PostgreSQL pool: %s", config.DATABASE_URL.split("@")[-1])
    pool = ConnectionPool(
        config.DATABASE_URL,
        min_size=config.DATABASE_POOL_MIN,
        max_size=config.DATABASE_POOL_MAX,
        open=True,
    )
    atexit.register(lambda: _close_pool(pool))
    return pool


def _close_pool(pool):
    """Close pool on shutdown."""
    if pool:
        logger.info("Closing PostgreSQL connection pool")
        pool.close()


def ensure_schema():
    """Create tables if they don't exist."""
    pool = get_db_pool()
    with pool.connection() as conn:
        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email         TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name  TEXT NOT NULL DEFAULT '',
                role          TEXT NOT NULL DEFAULT 'user',
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                is_active     BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)")

        # Conversations table (base schema without user_id for backward compat)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id            TEXT PRIMARY KEY,
                title         TEXT NOT NULL DEFAULT '',
                created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                message_count INTEGER NOT NULL DEFAULT 0,
                messages      JSONB NOT NULL DEFAULT '[]'::jsonb
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations (updated_at DESC)")

        # Add user_id column if missing (migration for existing DBs + new installs)
        conn.execute("""
            ALTER TABLE conversations ADD COLUMN IF NOT EXISTS
                user_id UUID REFERENCES users(id) ON DELETE CASCADE
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_conv_user_updated ON conversations (user_id, updated_at DESC)")

        # Refresh tokens table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash  TEXT UNIQUE NOT NULL,
                expires_at  TIMESTAMPTZ NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                revoked     BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens (token_hash)")

        # Shared conversations table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS shared_conversations (
                id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                conv_id     TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                share_token TEXT UNIQUE NOT NULL,
                created_by  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                expires_at  TIMESTAMPTZ,
                is_active   BOOLEAN NOT NULL DEFAULT TRUE
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_shared_conv_token ON shared_conversations (share_token)")

        # Clean up orphaned conversations (no user)
        conn.execute("DELETE FROM conversations WHERE user_id IS NULL")

        conn.commit()
    logger.info("Database schema verified")


def check_db_health() -> bool:
    """Test database connectivity for health check."""
    try:
        pool = get_db_pool()
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.warning("Database health check failed: %s", e)
        return False
