"""Create the application database if it does not already exist.

Usage:
    python -m app.scripts.init_db
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text

from app.core.config import settings


def create_database() -> bool:
    """Create the configured schema on the MySQL server."""
    engine = create_engine(settings.server_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{settings.db_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
                )
            )
        print(f"[ok] database '{settings.db_name}' is ready")
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"[error] could not create database '{settings.db_name}': {exc}")
        return False
    finally:
        engine.dispose()


def verify_connection() -> bool:
    """Verify the application can connect to the created schema."""
    engine = create_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar_one()
        print(f"[ok] connected to MySQL {version} as '{settings.db_user}'")
        return True
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"[error] connection check failed: {exc}")
        return False
    finally:
        engine.dispose()


def main() -> int:
    print(f"Target server : {settings.db_host}:{settings.db_port}")
    print(f"Target schema : {settings.db_name}")
    if not create_database():
        return 1
    if not verify_connection():
        return 1
    print("[done] database initialisation complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
