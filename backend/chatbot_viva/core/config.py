"""Configuration settings for the Vietnamese Legal RAG Chatbot."""

import logging
import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load environment variables (override=True to prioritize .env file over
# system env)
load_dotenv(override=True)

logger = logging.getLogger(__name__)

# Base directory
BASE_DIR = Path(__file__).parent.parent.parent.parent

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # For weather data

# Model Configuration
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-nano")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
TEMPERATURE = max(0.0, min(2.0, float(os.getenv("TEMPERATURE", "0"))))

# Multi-LLM Providers (optional - fallback to OpenAI if not set)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

# Provider preference: "openai", "gemini", "anthropic"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()

# Per-provider model overrides (cheap = fast/cheap tasks, quality = main answers)
OPENAI_MODEL_CHEAP = os.getenv("OPENAI_MODEL_CHEAP", "gpt-4.1-nano")
OPENAI_MODEL_QUALITY = os.getenv("OPENAI_MODEL_QUALITY", "")  # defaults to LLM_MODEL
ANTHROPIC_MODEL_CHEAP = os.getenv("ANTHROPIC_MODEL_CHEAP", "claude-3-haiku-20240307")
ANTHROPIC_MODEL_QUALITY = os.getenv("ANTHROPIC_MODEL_QUALITY", "")
GOOGLE_MODEL_CHEAP = os.getenv("GOOGLE_MODEL_CHEAP", "")
GOOGLE_MODEL_QUALITY = os.getenv("GOOGLE_MODEL_QUALITY", "")

# Cache Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
CACHE_TTL = max(0, int(os.getenv("CACHE_TTL", "3600")))

# Re-ranking Configuration
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_TOP_K = max(1, int(os.getenv("RERANK_TOP_K", "4")))

# Vector Store Configuration (Qdrant)
VECTORSTORE_COLLECTION_NAME = os.getenv(
    "VECTORSTORE_COLLECTION_NAME", "legal_documents"
)
VECTORSTORE_PATH = BASE_DIR / "qdrant_db"
QDRANT_URL = os.getenv("QDRANT_URL", None)  # If None, use local embedded mode
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)  # For cloud/server mode
QDRANT_TIMEOUT = max(30, int(os.getenv("QDRANT_TIMEOUT", "300")))
VECTORSTORE_BATCH_SIZE = max(10, int(os.getenv("VECTORSTORE_BATCH_SIZE", "100")))

# MongoDB Configuration
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/legal_database")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "legal_database")
MONGODB_COLLECTION_NAME = os.getenv("MONGODB_COLLECTION_NAME", "all_documents")

# Retriever Configuration
RETRIEVER_K = max(1, int(os.getenv("RETRIEVER_K", "4")))
MIN_SIMILARITY_SCORE = max(0.0, min(1.0, float(os.getenv("MIN_SIMILARITY_SCORE", "0.45"))))
MIN_LEGAL_SCORE = max(0.0, min(1.0, float(os.getenv("MIN_LEGAL_SCORE", "0.66"))))
MAX_CONTEXT_MESSAGES = max(1, int(os.getenv("MAX_CONTEXT_MESSAGES", "10")))
RAG_FETCH_K = max(1, int(os.getenv("RAG_FETCH_K", "8")))
RAG_TIMEOUT = max(5, int(os.getenv("RAG_TIMEOUT", "30")))
WEB_TIMEOUT = max(5, int(os.getenv("WEB_TIMEOUT", "60")))
MAX_RECURSIVE_REFS = max(0, int(os.getenv("MAX_RECURSIVE_REFS", "5")))
MAX_RECURSIVE_DEPTH = max(1, int(os.getenv("MAX_RECURSIVE_DEPTH", "2")))

# Web Search Configuration
MAX_WEB_SEARCH_RESULTS = 3

# Legal Web Search Configuration
LEGAL_WEB_TARGET_PAGES = int(os.getenv("LEGAL_WEB_TARGET_PAGES", "10"))
LEGAL_WEB_RAW_PER_QUERY = int(os.getenv("LEGAL_WEB_RAW_PER_QUERY", "8"))
LEGAL_WEB_MAX_CONTEXT_CHARS = int(os.getenv("LEGAL_WEB_MAX_CONTEXT_CHARS", "25000"))

# PostgreSQL Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://chatbot:changeme@localhost:5432/chatbot_db")
DATABASE_POOL_MIN = max(1, int(os.getenv("DATABASE_POOL_MIN", "2")))
DATABASE_POOL_MAX = max(2, int(os.getenv("DATABASE_POOL_MAX", "10")))

# Logging Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Auth Configuration
API_KEY = os.getenv("API_KEY")  # If not set, auth is disabled

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", "900"))  # 15 min
JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRES", "604800"))  # 7 days
JWT_ALGORITHM = "HS256"
PASSWORD_MIN_LENGTH = int(os.getenv("PASSWORD_MIN_LENGTH", "8"))
AUTH_RATE_LIMIT_MAX = int(os.getenv("AUTH_RATE_LIMIT_MAX", "10"))
AUTH_RATE_LIMIT_WINDOW = int(os.getenv("AUTH_RATE_LIMIT_WINDOW", "300"))  # 5 min

# Rate Limiting Configuration
RATE_LIMIT_MAX = int(os.getenv("RATE_LIMIT_MAX", "30"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Validation Configuration
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "5000"))
MAX_MESSAGES_COUNT = int(os.getenv("MAX_MESSAGES_COUNT", "100"))

# Cache Configuration (extended)
CACHE_TTL_REALTIME = int(os.getenv("CACHE_TTL_REALTIME", "300"))
CACHE_MAX_MEMORY_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "500"))

# Langfuse Configuration
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "cloud")


def validate_config() -> List[str]:
    """Validate configuration on startup. Returns list of warnings/errors."""
    errors = []

    # Check at least one LLM provider is configured
    has_provider = any([OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY])
    if not has_provider:
        errors.append(
            "CRITICAL: No LLM provider configured. "
            "Set at least one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY"
        )

    # Check embedding key (required for Qdrant)
    if not OPENAI_API_KEY:
        errors.append(
            "WARNING: OPENAI_API_KEY not set — embeddings (text-embedding-3-small) will fail"
        )

    # Check web search
    if not TAVILY_API_KEY:
        errors.append("WARNING: TAVILY_API_KEY not set — web search disabled")

    # Check LLM provider validity
    if LLM_PROVIDER not in ("openai", "gemini", "anthropic", "google"):
        errors.append(f"WARNING: Unknown LLM_PROVIDER '{LLM_PROVIDER}', defaulting to openai")

    # Check database URL
    if not DATABASE_URL or not DATABASE_URL.startswith("postgresql"):
        errors.append("WARNING: DATABASE_URL not set or invalid — conversation storage may fail")

    # Check JWT secret
    if not JWT_SECRET_KEY:
        errors.append("WARNING: JWT_SECRET_KEY not set — user authentication disabled")
    
    # Check MongoDB
    if not MONGODB_URI:
        errors.append("WARNING: MONGODB_URI not set — BM25 hybrid search will fail")

    for err in errors:
        logger.warning(err)

    return errors
