import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(__file__).parent.parent / ".cache"
DEFAULT_TTL = 3600  # 1 hour


def _cache_key(key: str) -> str:
    return hashlib.md5(key.encode()).hexdigest()


def get(key: str) -> Optional[Any]:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(key)}.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    if data.get("expires_at", 0) < time.time():
        path.unlink(missing_ok=True)
        return None

    return data["value"]


def set(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{_cache_key(key)}.json"
    data = {
        "value": value,
        "expires_at": time.time() + ttl,
    }
    path.write_text(json.dumps(data, ensure_ascii=False))


def delete(key: str) -> None:
    path = CACHE_DIR / f"{_cache_key(key)}.json"
    path.unlink(missing_ok=True)


def clear() -> None:
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
