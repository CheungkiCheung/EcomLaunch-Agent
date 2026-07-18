"""Commerce schema creation helper for tests and local development."""

from sqlalchemy.ext.asyncio import AsyncEngine

from app.commerce.persistence import models as _models
from app.commerce.persistence.base import CommerceBase

_ = _models


async def create_commerce_schema(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(CommerceBase.metadata.create_all)
