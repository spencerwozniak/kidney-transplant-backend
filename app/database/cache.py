"""
In-memory cache with TTL for storage layer
Reduces file I/O for frequently accessed data
"""
import time
from typing import Any, Dict, Optional, Tuple
from threading import Lock


class TTLCache:
    """
    Thread-safe in-memory cache with TTL (Time To Live)
    """
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self._lock:
            if key in self._cache:
                value, expiry = self._cache[key]
                if time.time() < expiry:
                    return value
                else:
                    # Expired, remove it
                    del self._cache[key]
            return None
    
    def set(self, key: str, value: Any):
        """Set value in cache with TTL"""
        with self._lock:
            expiry = time.time() + self.ttl
            self._cache[key] = (value, expiry)
    
    def invalidate(self, key: str):
        """Remove key from cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def clear(self):
        """Clear all cache entries"""
        with self._lock:
            self._cache.clear()


# Global cache instances with 60s TTL
_patient_cache = TTLCache(ttl_seconds=60)
_status_cache = TTLCache(ttl_seconds=60)
_checklist_cache = TTLCache(ttl_seconds=60)


def get_patient_cache() -> TTLCache:
    return _patient_cache


def get_status_cache() -> TTLCache:
    return _status_cache


def get_checklist_cache() -> TTLCache:
    return _checklist_cache
