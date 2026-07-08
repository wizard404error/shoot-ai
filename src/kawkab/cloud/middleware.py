"""FastAPI middleware for rate limiting, pagination, and security."""
from __future__ import annotations

import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


import os

class RateLimitMiddleware:
    """Token-bucket rate limiter per IP + endpoint prefix.
    
    Limits: analysis=5/min, export=10/min, search=30/min, general=60/min.
    Set KAWKAB_RATE_LIMIT_DISABLE=1 to disable for tests.
    """
    
    def __init__(self, app: FastAPI):
        self.app = app
        self.disabled = os.environ.get("KAWKAB_RATE_LIMIT_DISABLE") == "1"
        self._buckets: dict[str, dict] = defaultdict(lambda: {"tokens": 60, "last_refill": time.time()})
        self._limits = {
            "/api/v1/matches/": 30,
            "/api/v1/analysis": 5,
            "/api/v1/recruitment": 30,
            "/api/v1/webhooks": 10,
            "/api/v1/streaming": 10,
            "/api/v1/monitoring": 30,
            "/auth/": 10,
            "/sync/": 20,
            "/teams": 20,
        }
        self._default_limit = 60
    
    def _get_limit(self, path: str) -> int:
        for prefix, limit in self._limits.items():
            if path.startswith(prefix):
                return limit
        return self._default_limit
    
    async def __call__(self, scope, receive, send):
        if self.disabled or scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        request = Request(scope, receive)
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        
        limit = self._get_limit(path)
        key = f"{client_ip}:{path.split('/')[3] if len(path.split('/')) > 3 else 'general'}"
        now = time.time()
        bucket = self._buckets[key]
        
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(limit, bucket["tokens"] + elapsed * (limit / 60.0))
        bucket["last_refill"] = now
        
        if bucket["tokens"] < 1:
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_s": 60},
            )
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = "0"
            response.headers["Retry-After"] = "60"
            await response(scope, receive, send)
            return
        
        bucket["tokens"] -= 1
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                headers.append((b"X-RateLimit-Limit", str(limit).encode()))
                headers.append((b"X-RateLimit-Remaining", str(int(bucket["tokens"])).encode()))
                message["headers"] = headers
            await send(message)
        
        await self.app(scope, receive, send_wrapper)
