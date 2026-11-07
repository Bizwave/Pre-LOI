"""Database core (P2): SQLite in the data folder now, Postgres-compatible for later.

    from bizwave_preloi.db.session import session_scope
    from bizwave_preloi.db import repo
    with session_scope() as s:
        repo.transition(s, "acme-hvac", "ready", by="chan")

Schema changes only through Alembic migrations in db/migrations/versions/ (migrate.upgrade()).
Other code writes only through db/repo.py. Plan: tasks/plans/2026-11-06_p2_database.md
"""
