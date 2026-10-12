from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

from alembic import context
from app.config import settings
from app.database.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

database_url = make_url(str(settings.database_url)).set(drivername="postgresql+psycopg")
if (
    database_url.host
    and database_url.host.endswith("pooler.supabase.com")
    and database_url.port == 6543
):
    raise ValueError(
        "Alembic requires a direct or session-pooler connection, not transaction mode"
    )


def include_object(obj, name, type_, reflected, compare_to):
    # Supabase owns this external identity link, which is explicit in the migration.
    return not (type_ == "foreign_key_constraint" and name == "fk_users_auth_user")


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        database_url, poolclass=pool.NullPool, connect_args={"connect_timeout": 10}
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
