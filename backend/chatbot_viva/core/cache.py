"""
Response Cache with Redis backend and in-memory fallback.

Caches LLM responses to avoid redundant API calls for identical/similar queries.
- Redis: Persistent, shared across processes
- In-memory: Fallback when Redis unavailable (dict with LRU eviction)

Cache key = hash(normalized_query + context_fingerprint)
TTL configurable per query type.
"""

import hashlib
import json
import logging
import re
import time
import threading
import unicodedata
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from chatbot_viva.core import config as _cfg

logger = logging.getLogger(__name__)

# Config aliases (from centralized config)
REDIS_URL = _cfg.REDIS_URL
CACHE_TTL_SECONDS = _cfg.CACHE_TTL
CACHE_TTL_REALTIME = _cfg.CACHE_TTL_REALTIME
CACHE_MAX_MEMORY_ITEMS = _cfg.CACHE_MAX_MEMORY_ITEMS
CACHE_ENABLED = _cfg.CACHE_ENABLED


_VIETNAMESE_STOPWORDS = frozenset({
    "là", "của", "và", "các", "có", "được", "cho", "một", "này", "với",
    "trong", "không", "những", "đã", "để", "từ", "theo", "về", "khi",
    "thì", "đó", "cũng", "như", "tôi", "hỏi", "gì", "nào", "ạ",
})


def _normalize_query(query: str) -> str:
    """
    Normalize query for consistent cache keys.
    Sort words (loại stopwords) để "thuế nhà đất quy định" và
    "quy định thuế nhà đất" ra cùng cache key.
    """
    normalized = unicodedata.normalize("NFC", query.lower().strip())
    normalized = re.sub(r"\s+", " ", normalized)
    # Sort meaningful words để queries cùng nghĩa match nhau
    words = [w for w in normalized.split() if w not in _VIETNAMESE_STOPWORDS]
    return " ".join(sorted(words)) if words else normalized


def _hash_key(query: str, context_fingerprint: str = "") -> str:
    """Generate a cache key from query and optional context."""
    raw = f"{_normalize_query(query)}|{context_fingerprint}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class InMemoryCache:
    """Thread-safe LRU in-memory cache as Redis fallback."""

    def __init__(self, max_items: int = CACHE_MAX_MEMORY_ITEMS):
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_items = max_items
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._store[key]
                return None
            # Move to end = most recently used (proper LRU)
            self._store.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value: str, ttl: int = CACHE_TTL_SECONDS):
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            self._store[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
            }
            # Evict least recently used (first item)
            while len(self._store) > self._max_items:
                self._store.popitem(last=False)

    def delete(self, key: str):
        with self._lock:
            self._store.pop(key, None)

    def clear(self):
        with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._store)


class ResponseCache:
    """
    Unified cache interface.
    Tries Redis first, falls back to in-memory dict.
    """

    def __init__(self):
        self._redis = None
        self._memory = InMemoryCache()
        self._redis_available = False
        self._redis_lock = threading.Lock()

        if CACHE_ENABLED:
            self._try_connect_redis()

    def _try_connect_redis(self):
        """Attempt Redis connection (thread-safe). Silent fail to in-memory."""
        with self._redis_lock:
            if self._redis_available:
                return
            try:
                import redis
                self._redis = redis.from_url(
                    REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                self._redis.ping()
                self._redis_available = True
                logger.info("Redis cache connected: %s", REDIS_URL)
            except ImportError:
                logger.info("redis package not installed. Using in-memory cache.")
                self._redis_available = False
            except Exception as e:
                logger.info(
                    "Redis unavailable (%s). Using in-memory cache.", e
                )
                self._redis_available = False

    def get_response(
        self,
        query: str,
        context_fp: str = "",
    ) -> Optional[Dict[str, Any]]:
        if not CACHE_ENABLED:
            return None

        key = f"chat:{_hash_key(query, context_fp)}"

        if self._redis_available:
            try:
                data = self._redis.get(key)
                if data:
                    logger.info("Cache HIT (redis): %s...", key[:20])
                    return json.loads(data)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Redis cache corrupt for key %s, treating as miss", key[:20])
            except Exception as e:
                logger.warning("Redis get failed: %s", e)

        data = self._memory.get(key)
        if data:
            logger.info("Cache HIT (memory): %s...", key[:20])
            try:
                return json.loads(data)
            except (json.JSONDecodeError, ValueError):
                logger.warning("Memory cache corrupt for key %s, treating as miss", key[:20])
                self._memory.delete(key)

        logger.debug("Cache MISS: %s...", key[:20])
        return None

    def set_response(
        self,
        query: str,
        response: str,
        context_fp: str = "",
        sources: Optional[List] = None,
        is_realtime: bool = False,
    ):
        if not CACHE_ENABLED:
            return

        key = f"chat:{_hash_key(query, context_fp)}"
        ttl = CACHE_TTL_REALTIME if is_realtime else CACHE_TTL_SECONDS

        payload = json.dumps({
            "response": response,
            "sources": sources or [],
            "cached_at": time.time(),
            "query": query,
        }, ensure_ascii=False)

        if self._redis_available:
            try:
                self._redis.setex(key, ttl, payload)
                logger.debug(
                    "Redis cache SET: %s... (TTL=%ds)",
                    key[:16], ttl
                )
            except Exception as e:
                logger.warning("Redis set failed: %s", e)

        self._memory.set(key, payload, ttl)

    def invalidate(self, query: str, context_fp: str = ""):
        key = f"chat:{_hash_key(query, context_fp)}"

        if self._redis_available:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory.delete(key)

    def clear_all(self):
        if self._redis_available:
            try:
                for key in self._redis.scan_iter("chat:*"):
                    self._redis.delete(key)
            except Exception:
                pass
        self._memory.clear()

    @property
    def stats(self) -> Dict[str, Any]:
        info = {
            "enabled": CACHE_ENABLED,
            "backend": "redis" if self._redis_available else "memory",
            "memory_items": self._memory.size,
        }
        if self._redis_available:
            try:
                info["redis_keys"] = len(list(self._redis.scan_iter("chat:*")))
            except Exception:
                info["redis_keys"] = "error"
        return info


from chatbot_viva.core.singleton import singleton


@singleton
def get_response_cache() -> ResponseCache:
    """Get or create the global ResponseCache singleton (thread-safe)."""
    logger.info("Initializing Response Cache (enabled=%s)", CACHE_ENABLED)
    return ResponseCache()
