"""Database dependency injection."""
from typing import Annotated
from fastapi import Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.services.database import get_db


async def get_db_client() -> AsyncIOMotorDatabase:
    """FastAPI dependency: inject async MongoDB database."""
    return get_db()


DBDependency = Annotated[AsyncIOMotorDatabase, Depends(get_db_client)]
