"""Simple in-memory rate limiter for MVP."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request, HTTPException

from ..config.settings import RATE_LIMIT_RPM


class InMemoryRateLimiter:
    """
    Token-bucket style rate limiter keyed by client IP.
    Not suitable for multi-process production — use Redis-backed
    limiter for production deployments.
    """

    def __init__(self, requests_per_minute: int = RATE_LIMIT_RPM):
        self._rpm = requests_per_minute
        self._window = 60.0  # seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, request: Request) -> None:
        """Raise 429 if the client exceeded the rate limit."""
        ip = self._client_ip(request)
        now = time.monotonic()
        cutoff = now - self._window

        # Prune old entries
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

        if len(self._hits[ip]) >= self._rpm:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please wait before retrying.",
            )

        self._hits[ip].append(now)


# Singleton for the app
rate_limiter = InMemoryRateLimiter()
