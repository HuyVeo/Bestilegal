-- Chatbot Viva: Database schema

-- ══════════════════════════════════════════
-- Users table
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL DEFAULT '',
    role          TEXT NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

-- ══════════════════════════════════════════
-- Conversations table
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS conversations (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_count INTEGER NOT NULL DEFAULT 0,
    messages      JSONB NOT NULL DEFAULT '[]'::jsonb,
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE
);

-- Index for listing conversations by recency
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conv_user_updated ON conversations (user_id, updated_at DESC);

-- ══════════════════════════════════════════
-- Refresh tokens (multi-device, rotation)
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens (token_hash);

-- ══════════════════════════════════════════
-- Shared conversation links
-- ══════════════════════════════════════════
CREATE TABLE IF NOT EXISTS shared_conversations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conv_id     TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    share_token TEXT UNIQUE NOT NULL,
    created_by  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMPTZ,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_shared_conv_token ON shared_conversations (share_token);
