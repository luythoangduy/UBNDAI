"""Redis-first JSON cache with an in-process TTL fallback for local demos."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.config import settings

logger = logging.getLogger(__name__)
_MEMORY: dict[str, tuple[float, str]] = {}
_REDIS_CLIENT: Any | None = None
_REDIS_DISABLED_UNTIL = 0.0


@dataclass(frozen=True)
class CacheResult:
    value: dict[str, Any] | None
    backend: str
    hit: bool


async def get_json(key: str) -> CacheResult:
    client = await _redis_client()
    if client is not None:
        try:
            raw = await client.get(key)
            if raw is not None:
                return CacheResult(json.loads(raw), "redis", True)
            return CacheResult(None, "redis", False)
        except Exception:
            _disable_redis_temporarily()
            logger.warning("Redis cache unavailable; using memory fallback", exc_info=True)
    now = time.monotonic()
    cached = _MEMORY.get(key)
    if cached and cached[0] > now:
        return CacheResult(json.loads(cached[1]), "memory", True)
    if cached:
        _MEMORY.pop(key, None)
    return CacheResult(None, "memory", False)


async def set_json(key: str, value: dict[str, Any], *, ttl_seconds: int) -> str:
    raw = json.dumps(value, ensure_ascii=False, default=str)
    client = await _redis_client()
    if client is not None:
        try:
            await client.set(key, raw, ex=ttl_seconds)
            return "redis"
        except Exception:
            _disable_redis_temporarily()
            logger.warning("Redis cache write failed; using memory fallback", exc_info=True)
    _MEMORY[key] = (time.monotonic() + ttl_seconds, raw)
    return "memory"


async def _redis_client() -> Any | None:
    global _REDIS_CLIENT
    if not settings.redis_url or time.monotonic() < _REDIS_DISABLED_UNTIL:
        return None
    if _REDIS_CLIENT is None:
        try:
            from redis.asyncio import Redis

            _REDIS_CLIENT = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=settings.redis_connect_timeout_s,
                socket_timeout=settings.redis_connect_timeout_s,
            )
            await _REDIS_CLIENT.ping()
        except Exception:
            _REDIS_CLIENT = None
            _disable_redis_temporarily()
            return None
    return _REDIS_CLIENT


def _disable_redis_temporarily() -> None:
    global _REDIS_CLIENT, _REDIS_DISABLED_UNTIL
    _REDIS_CLIENT = None
    _REDIS_DISABLED_UNTIL = time.monotonic() + 30


def reset_cache() -> None:
    global _REDIS_CLIENT, _REDIS_DISABLED_UNTIL
    _MEMORY.clear()
    _REDIS_CLIENT = None
    _REDIS_DISABLED_UNTIL = 0.0
