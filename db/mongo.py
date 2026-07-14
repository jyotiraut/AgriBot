import certifi
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from config import get_settings
import logging

settings = get_settings()

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
_db: AsyncIOMotorDatabase = None









# ── Lifecycle ─────────────────────────────────────────────────────────────────

async def connect_db() -> None:
    """Connect to MongoDB and create all indexes."""
    global client, _db

    # using MongoDB URI directly from settings
    print(f"Connecting to MongoDB at {settings.mongodb_uri}")
    client = AsyncIOMotorClient(
        settings.mongodb_uri,
        tlsCAFile=certifi.where()
    )
    _db = client[settings.mongodb_db_name]
    print(f"Successfully connected to DB: {_db.name}")

    await client.admin.command("ping")
    logger.info(f"✅ Connected to MongoDB → {settings.mongodb_db_name}")

    await _create_indexes()


async def disconnect_db() -> None:
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed.")


async def _create_indexes() -> None:
    """Idempotent — safe to run every startup."""

    # users
    await _db.users.create_index(
        [("email", ASCENDING)], unique=True, name="unique_email"
    )

    # conversations
    await _db.conversations.create_index(
        [("user_id", ASCENDING), ("created_at", DESCENDING)],
        name="user_timeline",
    )
    await _db.conversations.create_index(
        [("session_id", ASCENDING)], name="session_lookup"
    )

    # farmer_profiles — sparse=True so null user_id docs don't conflict
    await _db.farmer_profiles.create_index(
        [("user_id", ASCENDING)], unique=True, sparse=True, name="unique_user_profile"
    )
    await _db.farmer_profiles.create_index(
        [("credit_score", DESCENDING)], name="score_ranking"
    )

    logger.info("✅ MongoDB indexes ready.")


# ── Accessor ──────────────────────────────────────────────────────────────────

def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised. Call connect_db() first.")
    return _db