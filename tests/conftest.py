import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import Integer, Text

from pzsd_bot.db import Session, engine
from pzsd_bot.model import metadata, pzsd_user


@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Create and teardown the test database."""
    # Modify schema to accommodate features sqlite doesn't support
    metadata.tables["pzsd_user"].columns["id"].server_default = None
    metadata.tables["pzsd_user"].columns["id"].type = Text()
    metadata.tables["ledger"].columns["id"].server_default = None
    metadata.tables["ledger"].columns["id"].type = Integer()
    metadata.tables["ledger"].columns["id"].autoincrement = True
    metadata.tables["ledger"].columns["bestower"].type = Text()
    metadata.tables["ledger"].columns["recipient"].type = Text()

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seed_users():
    """Seed the test database with users."""
    async with Session.begin() as session:
        test_users = [
            {
                "id": "1",
                "name": "bestower",
                "discord_snowflake": "1",
                "is_active": True,
                "point_giver": True,
            },
            {
                "id": "2",
                "name": "recipient",
                "discord_snowflake": "2",
                "is_active": True,
                "point_giver": True,
            },
            {
                "id": "3",
                "name": "recipient2",
                "discord_snowflake": "3",
                "is_active": True,
                "point_giver": True,
            },
            {
                "id": "4",
                "name": "abba-zaba",
                "discord_snowflake": None,
                "is_active": True,
                "point_giver": False,
            },
            {
                "id": "5",
                "name": "mcdonald's",
                "discord_snowflake": None,
                "is_active": True,
                "point_giver": False,
            },
            {
                "id": "6",
                "name": "name with spaces",
                "discord_snowflake": None,
                "is_active": True,
                "point_giver": False,
            },
            {
                "id": "7",
                "name": "bestower_inactive",
                "discord_snowflake": "7",
                "is_active": False,
                "point_giver": True,
            },
            {
                "id": "8",
                "name": "bestower_non_point_giver",
                "discord_snowflake": "8",
                "is_active": True,
                "point_giver": False,
            },
            {
                "id": "9",
                "name": "recipient_inactive",
                "discord_snowflake": "9",
                "is_active": False,
                "point_giver": True,
            },
            {
                "id": "10",
                "name": "recipient_non_point_giver",
                "discord_snowflake": "10",
                "is_active": True,
                "point_giver": False,
            },
        ]
        await session.execute(pzsd_user.insert().values(test_users))


@pytest.fixture
def mock_bot():
    mock_bot = MagicMock()

    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock()

    mock_bot.get_channel.return_value = mock_channel

    return mock_bot


@pytest.fixture
def mock_db_session():
    mock_session = AsyncMock()

    with patch(
        "pzsd_bot.db.Session.begin",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session)),
    ):
        yield mock_session


@pytest.fixture
def mock_bestower():
    """Mock bestower pzsd_user."""
    user = AsyncMock()
    user.id = str(uuid4())
    user.name = "bestower"
    user.discord_snowflake = "12345"
    user.is_active = True
    user.point_giver = True
    return user


@pytest.fixture
def mock_recipient():
    """Mock recipient pzsd_user."""
    user = AsyncMock()
    user.id = str(uuid4())
    user.name = "recipient"
    user.discord_snowflake = "56789"
    user.is_active = True
    user.point_giver = True
    return user
