"""Programmatic entry point for the independent Commerce Alembic branch."""

from pathlib import Path

from alembic import command
from alembic.config import Config

_MIGRATIONS_DIR = Path(__file__).resolve().parent


def commerce_alembic_config(sqlalchemy_url: str) -> Config:
    config = Config(str(_MIGRATIONS_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(_MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", sqlalchemy_url.replace("%", "%%"))
    return config


def upgrade_commerce_schema(sqlalchemy_url: str, revision: str = "head") -> None:
    command.upgrade(commerce_alembic_config(sqlalchemy_url), revision)


def downgrade_commerce_schema(sqlalchemy_url: str, revision: str = "base") -> None:
    command.downgrade(commerce_alembic_config(sqlalchemy_url), revision)
