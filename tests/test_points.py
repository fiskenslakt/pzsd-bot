from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from sqlalchemy import select

from pzsd_bot.cogs.points.points import EVERYONE_KEYWORD, Points
from pzsd_bot.db import Session
from pzsd_bot.model import ledger, pzsd_user
from pzsd_bot.settings import POINT_MAX_VALUE, POINT_MIN_VALUE, Emoji


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_recipient_id,mock_recipient_name,mock_point_amount",
    [
        ("2", "recipient", "1"),
        ("4", "Abba-Zaba", "1,000"),
        ("5", "McDonald's", "-42"),
        ("6", '"name with spaces"', "0"),
    ],
)
async def test_successful_point_transaction__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
    mock_recipient_id: str,
    mock_recipient_name: str,
    mock_point_amount: str,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=1)  # bestower discord_snowflake
    mock_message.content = f"{mock_point_amount} points to {mock_recipient_name}"

    _, recipient_name, _ = await points_cog.get_transaction_info(mock_message)
    assert recipient_name == mock_recipient_name.strip('"')

    await points_cog.on_message(mock_message)

    async with Session.begin() as session:
        result = await session.execute(select(ledger))
        rows = result.fetchall()

    assert len(rows) == 1
    row = rows[0]

    assert row.bestower == "1"  # bestower id
    assert row.recipient == mock_recipient_id
    assert row.points == int(mock_point_amount.replace(",", ""))

    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_invalid_recipient__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that you can't bestow points to a user that isn't in the user table."""
    recipient_name = "foobar"
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=1)  # bestower discord_snowflake
    mock_message.content = f"1 point to {recipient_name}"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower"
    assert bestower_is_valid is True

    recipient, recipient_is_valid = await points_cog.get_recipient(
        mock_message,
        bestower,
        recipient_name,
        None,
        pzsd_user.c.name == recipient_name.lower(),
    )
    assert recipient is None
    assert recipient_is_valid is False

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_inactive_recipient__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that you can't bestow points to a user that is in the user table but isn't active."""
    recipient_name = "recipient_inactive"
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=1)  # bestower discord_snowflake
    mock_message.content = f"1 point to {recipient_name}"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower"
    assert bestower_is_valid is True

    recipient, recipient_is_valid = await points_cog.get_recipient(
        mock_message,
        bestower,
        recipient_name,
        None,
        pzsd_user.c.name == recipient_name.lower(),
    )
    assert recipient.id == "9"  # recipient_inactive id
    assert recipient_is_valid is False

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_invalid_bestower__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that a discord user not in the user table can't bestow points."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=42)  # id isn't in user table
    mock_message.content = "1 point to foobar"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower is None
    assert bestower_is_valid is False

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_inactive_bestower__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that a discord user in the user table that's inactive can't bestow points."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=7)  # bestower_inactive discord_snowflake
    mock_message.content = "1 point to foobar"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower_inactive"
    assert bestower_is_valid is False

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_bestower_non_point_giver__standard_syntax(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that a discord user in the user table that's not a point giver can't bestow points."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=8)  # bestower_non_point_giver discord_snowflake
    mock_message.content = "1 point to foobar"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower_non_point_giver"
    assert bestower_is_valid is False

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_successful_point_transaction_to_everyone(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that bestowing points to "everyone" bestows points to every active point giver in the user table."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=1)  # bestower discord_snowflake
    mock_message.content = f"1 point to {EVERYONE_KEYWORD}"

    _, recipient_name, _ = await points_cog.get_transaction_info(mock_message)
    assert recipient_name == EVERYONE_KEYWORD

    points_cog.get_recipient = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.get_recipient.assert_not_called()

    async with Session.begin() as session:
        result = await session.execute(select(ledger))
        rows = result.fetchall()

    assert len(rows) == 2
    assert {rows[0].recipient, rows[1].recipient} == {
        "2",
        "3",
    }  # ids of recipient and recipient2
    assert {rows[0].bestower, rows[1].bestower} == {"1"}  # id of bestower
    assert {rows[0].points, rows[1].points} == {1}  # everyone gets 1 point

    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
@pytest.mark.parametrize("mock_point_amount", ["1", "1,000", "-42", "0"])
async def test_successful_point_transaction__reply_syntax(
    seed_users: None,
    mock_bot: MagicMock,
    mock_point_amount: str,
):
    points_cog = Points(mock_bot)

    mock_recipient_message = MagicMock(spec=discord.Message)
    mock_recipient_message.author = MagicMock(id=2)  # recipient discord_snowflake

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = f"{mock_point_amount} point"
    mock_message.author = MagicMock(id=1)
    mock_message.reference = MagicMock()

    points_cog.bot.get_message = MagicMock(return_value=mock_recipient_message)

    recipient_id, recipient_name, _ = await points_cog.get_transaction_info(
        mock_message
    )
    assert recipient_name is None
    assert recipient_id == "2"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower"
    assert bestower_is_valid is True

    recipient, recipient_is_valid = await points_cog.get_recipient(
        mock_message,
        bestower,
        None,
        recipient_id,
        pzsd_user.c.discord_snowflake == recipient_id,
    )
    assert recipient.name == "recipient"
    assert recipient_is_valid is True

    await points_cog.on_message(mock_message)

    async with Session.begin() as session:
        result = await session.execute(select(ledger))
        rows = result.fetchall()

    assert len(rows) == 1
    row = rows[0]

    assert row.bestower == "1"  # bestower id
    assert row.recipient == "2"  # recipient id
    assert row.points == int(mock_point_amount.replace(",", ""))

    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
async def test_self_point_violation(
    seed_users: None,
    mock_bot: MagicMock,
):
    """Test that a user can't bestow points to themselves."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.author = MagicMock(id=1)  # bestower id
    mock_message.content = "1 point to bestower"

    _, recipient_name, _ = await points_cog.get_transaction_info(mock_message)
    assert recipient_name == "bestower"

    bestower, bestower_is_valid = await points_cog.get_bestower(mock_message)
    assert bestower.name == "bestower"
    assert bestower_is_valid is True

    recipient, recipient_is_valid = await points_cog.get_recipient(
        mock_message,
        bestower,
        recipient_name,
        None,
        pzsd_user.c.name == recipient_name.lower(),
    )
    assert recipient.name == "bestower"
    assert recipient_is_valid is True

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.nopers)


@pytest.mark.asyncio
@pytest.mark.parametrize("point_amount", [POINT_MAX_VALUE + 1, POINT_MIN_VALUE - 1])
async def test_excessive_point_violation(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
    mock_recipient: AsyncMock,
    point_amount: int,
):
    """Test that a user can't bestow more than the max allowed points."""
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = f"{point_amount} points to foobar"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, True))

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.nopers)
