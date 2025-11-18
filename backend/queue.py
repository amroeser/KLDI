"""RQ queue and Redis connection setup."""
from __future__ import annotations

import os

import redis
from rq import Queue


def _create_redis_connection() -> redis.Redis:
    # Default local Redis; can be overridden via REDIS_URL
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.from_url(redis_url)


redis_conn = _create_redis_connection()

# Default queue used by the application
default_queue: Queue = Queue("default", connection=redis_conn)
