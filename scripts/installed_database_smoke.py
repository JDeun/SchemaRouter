from __future__ import annotations

import sqlite3
from importlib.metadata import version

from sqlalchemy import create_engine

from schemarouter import SchemaRouter


def run_smoke() -> dict[str, object]:
    connection = sqlite3.connect(":memory:")
    connection.execute(
        "CREATE TABLE local_items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    router = SchemaRouter()
    sqlite_keys = router.add_sqlite_database(
        connection,
        database_name="local",
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as db:
        db.exec_driver_sql(
            "CREATE TABLE server_items (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
    sqlalchemy_keys = router.add_sqlalchemy_database(
        engine,
        database_name="server",
        remote=False,
    )

    try:
        assert sqlite_keys == ("local.local_items",)
        assert sqlalchemy_keys == ("server.server_items",)
        return {
            "status": "success",
            "dependencies": {"sqlalchemy": version("sqlalchemy")},
            "adapters": ["sqlite", "sqlalchemy"],
        }
    finally:
        engine.dispose()
        connection.close()


def main() -> None:
    import json

    print(json.dumps(run_smoke(), sort_keys=True))


if __name__ == "__main__":
    main()
