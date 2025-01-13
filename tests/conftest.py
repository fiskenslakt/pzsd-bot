import logging
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL)


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
