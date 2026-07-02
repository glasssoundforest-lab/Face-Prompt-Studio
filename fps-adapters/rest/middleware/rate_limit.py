"""fps-adapters/rest/middleware/rate_limit.py — レート制限 ★v3.0"""
from __future__ import annotations
import time, threading
from collections import defaultdict, deque
from typing import Any, Callable
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class RateLimiter:
    """スライディングウィンドウ方式のレート制限器"""
    def __init__(self, max_requests: int = 100, window_sec: float = 60.0) -> None:
        self._max = max_requests; self._window = window_sec
        self._lock = threading.Lock()
        self._store: dict[str, deque] = defaultdict(deque)

    def check(self, key: str) -> tuple[bool, dict[str, Any]]:
        now = time.time()
        with self._lock:
            q = self._store[key]
            while q and now - q[0] > self._window:
                q.popleft()
            remaining = self._max - len(q)
            if remaining <= 0:
                reset = int(self._window - (now - q[0])) + 1
                return False, {"remaining": 0, "limit": self._max, "reset_after": reset}
            q.append(now)
            return True, {"remaining": remaining - 1, "limit": self._max,
                          "reset_after": int(self._window)}

    def reset(self, key: str) -> None:
        with self._lock: self._store.pop(key, None)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"tracked_keys": len(self._store), "max_requests": self._max,
                    "window_sec": self._window}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI レート制限ミドルウェア（APIキー別 / IP別）"""
    _EXCLUDE = frozenset(["/docs","/redoc","/openapi.json","/health","/favicon.ico"])

    def __init__(self, app: Any, anon_limit: int = 100, auth_limit: int = 1000,
                 window_sec: float = 60.0, enabled: bool = True) -> None:
        super().__init__(app)
        self._enabled    = enabled
        self._anon_limit = RateLimiter(anon_limit, window_sec)
        self._auth_limit = RateLimiter(auth_limit, window_sec)

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        if not self._enabled or request.url.path in self._EXCLUDE:
            return await call_next(request)
        api_key = request.headers.get("X-Api-Key", "")
        if api_key:
            limiter = self._auth_limit; key = f"auth:{api_key[:16]}"
        else:
            limiter = self._anon_limit
            key = f"ip:{request.client.host if request.client else 'unknown'}"
        allowed, info = limiter.check(key)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "reset_after": info["reset_after"]},
                headers={"X-RateLimit-Limit": str(info["limit"]),
                         "X-RateLimit-Remaining": "0",
                         "Retry-After": str(info["reset_after"])},
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"]     = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        return response
