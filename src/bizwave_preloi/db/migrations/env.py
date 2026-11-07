"""Alembic environment. Called through bizwave_preloi.db.migrate, which passes an open connection
(with the SQLite pragmas applied). Offline (SQL script) mode is not used."""
from alembic import context

from bizwave_preloi.db.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      render_as_batch=True,      # SQLite needs batch mode to alter columns later
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations are not supported; use bizwave_preloi.db.migrate.upgrade().")

connection = config.attributes.get("connection")
if connection is None:
    # Calling Alembic directly would fall back to the data folder's (live) database and skip the
    # safeguards in migrate.py (a named database for downgrade; one transaction; foreign-key check).
    raise RuntimeError("Run migrations through bizwave_preloi.db.migrate (upgrade, downgrade) or "
                       "`python -m bizwave_preloi.db`, not Alembic directly.")
_run(connection)
