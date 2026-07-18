from logging.config import fileConfig
import os
from sqlalchemy import engine_from_config, pool
from alembic import context
from src.services.persistence import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def _migration_database_url() -> str:
    """Return a synchronous SQLAlchemy URL suitable for Alembic."""
    database_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    if database_url.startswith("postgres://"):
        database_url = f"postgresql+psycopg://{database_url.removeprefix('postgres://')}"
    elif database_url.startswith("postgresql://"):
        database_url = (
            f"postgresql+psycopg://{database_url.removeprefix('postgresql://')}"
        )
    return database_url


# ConfigParser treats percent signs as interpolation markers. Doubling them keeps
# URL-encoded database passwords intact when Alembic reads the value back.
config.set_main_option("sqlalchemy.url", _migration_database_url().replace("%", "%%"))
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
