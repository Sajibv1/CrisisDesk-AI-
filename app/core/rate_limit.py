from __future__ import annotations

from collections import defaultdict, deque
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.response import error_response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests_per_minute: int) -> None:
        super().__init__(app)
        self.max_requests_per_minute = max_requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else "unknown"
        bucket = self._hits[client]
        now = time()
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= self.max_requests_per_minute:
            return error_response("Rate limit exceeded.", status_code=429)
        bucket.append(now)
        return await call_next(request)
