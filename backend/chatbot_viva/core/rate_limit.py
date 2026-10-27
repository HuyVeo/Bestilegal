"""In-memory sliding window rate limiting.

Framework-agnostic: RateLimiter class has no Flask/FastAPI dependency.
FastAPI integration is in core/dependencies.py.
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict

from chatbot_viva.core import config


class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(
        self,
        max_requests: int = 30,
        window_seconds: int = 60,
    ) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()
        self._check_count = 0

    def is_allowed(self, client_ip: str) -> bool:
        """Check if client_ip is within rate limit."""
        now = time.time()
        cutoff = now - self.window_seconds

        with self._lock:
            self._check_count += 1
            if self._check_count % 100 == 0:
                self._cleanup_stale(cutoff)

            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > cutoff
            ]

            if len(self._requests[client_ip]) >= self.max_requests:
                return False

            self._requests[client_ip].append(now)
            return True

    def _cleanup_stale(self, cutoff: float) -> None:
        """Remove stale entries (called under lock)."""
        stale = [
            ip for ip, times in self._requests.items()
            if all(t <= cutoff for t in times)
        ]
        for ip in stale:
            del self._requests[ip]

    def cleanup(self) -> None:
        """Remove stale entries (public API)."""
        cutoff = time.time() - self.window_seconds
        with self._lock:
            self._cleanup_stale(cutoff)
