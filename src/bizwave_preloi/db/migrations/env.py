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
    from bizwave_preloi.db.session import get_engine
    with get_engine(config.get_main_option("sqlalchemy.url") or None).begin() as conn:
        _run(conn)
else:
    _run(connection)
