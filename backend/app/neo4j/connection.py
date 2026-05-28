from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from neo4j import GraphDatabase

from app.config import settings


@dataclass(frozen=True)
class Neo4jConnectionConfig:
    uri: str
    user: str
    password: str

    @classmethod
    def from_settings(cls) -> "Neo4jConnectionConfig":
        return cls(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )


_DRIVER_HOLDER: dict[str, Any] = {}
_DRIVER_LOCK = RLock()


def create_neo4j_driver(config: Neo4jConnectionConfig | None = None) -> Any:
    resolved_config = config or Neo4jConnectionConfig.from_settings()
    return GraphDatabase.driver(
        resolved_config.uri,
        auth=(resolved_config.user, resolved_config.password),
    )


def get_neo4j_driver() -> Any:
    with _DRIVER_LOCK:
        driver = _DRIVER_HOLDER.get("driver")
        if driver is None:
            driver = create_neo4j_driver()
            _DRIVER_HOLDER["driver"] = driver
        return driver


def close_neo4j_driver() -> None:
    with _DRIVER_LOCK:
        driver = _DRIVER_HOLDER.pop("driver", None)
    if driver is None:
        return
    close = getattr(driver, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            return


def reset_neo4j_driver_cache() -> None:
    with _DRIVER_LOCK:
        _DRIVER_HOLDER.pop("driver", None)


def check_neo4j_health(driver: Any | None) -> str:
    if driver is None:
        return "unavailable"

    try:
        driver.verify_connectivity()
    except Exception:
        return "unavailable"
    return "ok"
