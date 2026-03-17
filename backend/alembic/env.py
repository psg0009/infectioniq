import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from sqlalchemy import String
from app.core.database import Base
from app.models import models
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.consent import PatientConsent
from app.services.clinical_validation import ValidationSession, ValidationObservation
from app.models.models import UUID36
from app.config import settings

target_metadata = Base.metadata

# Set DATABASE_URL from app settings (overrides alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def render_item(type_, obj, autogen_context):
    """Render UUID36 as sa.String(36) in migrations"""
    if type_ == "type" and isinstance(obj, UUID36):
        return "sa.String(length=36)"
    return False


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, render_item=render_item)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata, render_item=render_item)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
