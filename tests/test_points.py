from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from sqlalchemy import text

from pzsd_bot.cogs.points.points import EVERYONE_KEYWORD, Points
from pzsd_bot.model import ledger, pzsd_user
from pzsd_bot.settings import POINT_MAX_VALUE, POINT_MIN_VALUE, Emoji


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_recipient_name,mock_point_amount",
    [
        ("foobar", "1"),
        ("Abba-Zaba", "1,000"),
        ("McDonald's", "-42"),
        ('"name with spaces"', "0"),
    ],
)
async def test_successful_point_transaction__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
    mock_recipient: AsyncMock,
    mock_recipient_name: str,
    mock_point_amount: str,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = f"{mock_point_amount} points to {mock_recipient_name}"

    _, recipient_name, _ = await points_cog.get_transaction_info(mock_message)
    assert recipient_name == mock_recipient_name.strip('"')

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, True))

    with patch("pzsd_bot.cogs.points.points.insert") as mock_insert:
        await points_cog.on_message(mock_message)

    mock_db_session.execute.assert_called_once_with(
        mock_insert(ledger).values(
            bestower=mock_bestower.id,
            recipient=mock_recipient.id,
            points=int(mock_point_amount.replace(",", "")),
        )
    )
    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_invalid_recipient__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point to foobar"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(None, False))

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_invalid_bestower__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_recipient: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point to foobar"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(None, False))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, True))

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_inactive_recipient__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
    mock_recipient: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point to foobar"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, False))

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_unsuccessful_point_transaction_inactive_bestower__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
    mock_recipient: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point to foobar"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, False))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, True))

    points_cog.bestow_points = AsyncMock()

    await points_cog.on_message(mock_message)

    points_cog.bestow_points.assert_not_called()
    mock_message.add_reaction.assert_called_once_with(Emoji.cross_mark)


@pytest.mark.asyncio
async def test_successful_point_transaction_to_everyone__standard_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = f"1 point to {EVERYONE_KEYWORD}"

    _, recipient_name, _ = await points_cog.get_transaction_info(mock_message)
    assert recipient_name == EVERYONE_KEYWORD

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock()

    with (
        patch("pzsd_bot.cogs.points.points.insert") as mock_insert,
        patch("pzsd_bot.cogs.points.points.select") as mock_select,
    ):
        await points_cog.on_message(mock_message)

    points_cog.get_recipient.assert_not_called()

    mock_users_select = mock_select(
        text(f"'{mock_bestower.id}'"),
        pzsd_user.c.id,
        text("1"),
    ).where(
        (pzsd_user.c.is_active == True)
        & (pzsd_user.c.id != mock_bestower.id)
        & (pzsd_user.c.discord_snowflake != None)
        & (pzsd_user.c.point_giver == True)
    )
    mock_db_session.execute.assert_called_once_with(
        mock_insert(ledger).from_select(
            ["bestower", "recipient", "points"], mock_users_select
        )
    )
    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
@pytest.mark.parametrize("mock_point_amount", ["1", "1,000", "-42", "0"])
async def test_successful_point_transaction__reply_syntax(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
    mock_recipient: AsyncMock,
    mock_point_amount: str,
):
    points_cog = Points(mock_bot)

    mock_recipient_message = MagicMock(spec=discord.Message)
    mock_recipient_message.author = MagicMock()
    mock_recipient_message.author.id = int(mock_recipient.discord_snowflake)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point"
    mock_message.reference = MagicMock()

    points_cog.bot.get_message = MagicMock(return_value=mock_recipient_message)

    recipient_id, recipient_name, _ = await points_cog.get_transaction_info(
        mock_message
    )
    assert recipient_name is None
    assert recipient_id == mock_recipient.discord_snowflake

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(mock_recipient, True))

    with patch("pzsd_bot.cogs.points.points.insert") as mock_insert:
        await points_cog.on_message(mock_message)

    mock_db_session.execute.assert_called_once_with(
        mock_insert(ledger).values(
            bestower=mock_bestower.id,
            recipient=mock_recipient.id,
            points=int(mock_point_amount.replace(",", "")),
        )
    )
    mock_message.add_reaction.assert_called_once_with(Emoji.check_mark)


@pytest.mark.asyncio
async def test_self_point_violation(
    mock_bot: MagicMock,
    mock_db_session: AsyncMock,
    mock_bestower: AsyncMock,
):
    points_cog = Points(mock_bot)

    mock_message = MagicMock(spec=discord.Message)
    mock_message.content = "1 point to bestower"

    # mock db calls that fetch pzsd_user
    points_cog.get_bestower = AsyncMock(return_value=(mock_bestower, True))
    points_cog.get_recipient = AsyncMock(return_value=(mock_bestower, True))

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
