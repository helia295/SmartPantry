from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from time import time
from typing import Deque

from fastapi import Request

from app.core.config import Settings


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    path: str
    methods: tuple[str, ...]
    limit: int
    window_seconds: int


class InMemoryRateLimiter:
    """
    Small in-memory limiter for single-instance deployments.

    This is not a distributed/global limiter. It is still useful for:
    - slowing brute-force login attempts
    - reducing easy abuse of image uploads
    - giving the app a real first line of protection without adding Redis yet
    """

    def __init__(self, settings: Settings) -> None:
        self._rules = (
            RateLimitRule(
                name="auth_login",
                path="/auth/login",
                methods=("POST",),
                limit=max(settings.auth_rate_limit_requests, 1),
                window_seconds=max(settings.auth_rate_limit_window_seconds, 1),
            ),
            RateLimitRule(
                name="auth_register",
                path="/auth/register",
                methods=("POST",),
                limit=max(settings.register_rate_limit_requests, 1),
                window_seconds=max(settings.register_rate_limit_window_seconds, 1),
            ),
            RateLimitRule(
                name="image_upload",
                path="/images",
                methods=("POST",),
                limit=max(settings.image_upload_rate_limit_requests, 1),
                window_seconds=max(settings.image_upload_rate_limit_window_seconds, 1),
            ),
        )
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = Lock()

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()

    def check(self, request: Request) -> tuple[RateLimitRule, int] | None:
        rule = self._match_rule(request)
        if rule is None:
            return None

        key = self._bucket_key(rule, request)
        now = time()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = now - rule.window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.limit:
                retry_after = max(1, int(bucket[0] + rule.window_seconds - now))
                return rule, retry_after

            bucket.append(now)
        return None

    def _match_rule(self, request: Request) -> RateLimitRule | None:
        path = request.url.path
        method = request.method.upper()
        for rule in self._rules:
            if path == rule.path and method in rule.methods:
                return rule
        return None

    def _bucket_key(self, rule: RateLimitRule, request: Request) -> str:
        forwarded_for = request.headers.get("x-forwarded-for", "")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"
        return f"{rule.name}:{client_ip}"
