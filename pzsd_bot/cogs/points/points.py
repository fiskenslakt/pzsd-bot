import logging
from datetime import datetime
from typing import Tuple

import discord
from discord import Bot, Message
from discord.ext.commands import Cog
from sqlalchemy import insert, select, text

from pzsd_bot.db import Session
from pzsd_bot.model import ledger, pzsd_user
from pzsd_bot.settings import (
    POINT_MAX_VALUE,
    POINT_MIN_VALUE,
    Channels,
    Colors,
    PointsSettings,
)

EVERYONE_KEYWORD = "everyone"

logger = logging.getLogger(__name__)

LeaderboardField = Tuple[int, str, int]


class Points(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author == self.bot.user:
            return

        if match := PointsSettings.point_pattern.search(message.content):
            recipient_name = match["recipient_name"]
            if recipient_name is not None:
                recipient_name = recipient_name.strip('"')
            recipient_id = match["recipient_id"]
        elif message.reference and (
            match := PointsSettings.reply_point_pattern.search(message.content)
        ):
            original_message = self.bot.get_message(message.reference.message_id)
            # message wasn't cached, make api call
            if original_message is None:
                original_message = await message.channel.fetch_message(
                    message.reference.message_id
                )
            recipient_name = None
            recipient_id = str(original_message.author.id)
        else:
            return

        point_amount = int(match["point_amount"].replace(",", ""))
        pretty_point_amount = format(point_amount, ",")

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(
                    pzsd_user.c.discord_snowflake == str(message.author.id)
                )
            )

            bestower = result.one_or_none()

            if bestower is None:
                logger.info(
                    "User '%s' with snowflake '%s' tried to bestow points but wasn't in the user table",
                    message.author.name,
                    message.author.id,
                )
                return

            if not bestower.is_active:
                logger.warning(
                    "User '%s' with snowflake '%s' tried to bestow points but is currently inactive",
                    bestower.name,
                    bestower.discord_snowflake,
                )
                return

            if not bestower.point_giver:
                logger.info(
                    "User '%s' with snowflake '%s' tried to bestow points but isn't a point giver",
                    bestower.name,
                    bestower.discord_snowflake,
                )
                return

            is_to_everyone = False
            if recipient_name is None:
                condition = pzsd_user.c.discord_snowflake == recipient_id
            elif recipient_name.lower() == EVERYONE_KEYWORD:
                is_to_everyone = True
            else:
                condition = pzsd_user.c.name == recipient_name.lower()

            if not is_to_everyone:
                result = await session.execute(select(pzsd_user).where(condition))

                recipient = result.one_or_none()

                if recipient is None:
                    logger.info(
                        "%s tried to bestow points to '%s' but they weren't in the user table",
                        bestower.name,
                        recipient_name or recipient_id,
                    )
                    return

                if not recipient.is_active:
                    logger.info(
                        "%s tried to bestow points to '%s' but they were inactive",
                        bestower.name,
                        recipient_name or recipient_id,
                    )
                    return

        excessive_point_violation = (
            not POINT_MIN_VALUE <= point_amount <= POINT_MAX_VALUE
        )
        if excessive_point_violation:
            logger.info(
                "%s tried to give %s more than the max allowed points (%s)",
                bestower.name,
                recipient.name if not is_to_everyone else EVERYONE_KEYWORD,
                pretty_point_amount,
            )
            return

        self_point_violation = is_to_everyone is False and bestower.id == recipient.id
        if not self_point_violation:
            logger.info(
                "%s awarding %s point(s) to %s",
                bestower.name,
                pretty_point_amount,
                recipient.name if not is_to_everyone else EVERYONE_KEYWORD,
            )
            if not is_to_everyone:
                async with Session.begin() as session:
                    await session.execute(
                        insert(ledger).values(
                            bestower=bestower.id,
                            recipient=recipient.id,
                            points=point_amount,
                        )
                    )
                logger.info("Added point transaction to ledger")
            else:
                async with Session.begin() as session:
                    users = select(
                        text(f"'{bestower.id}'"),
                        pzsd_user.c.id,
                        text(str(point_amount)),
                    ).where(
                        (pzsd_user.c.is_active == True)
                        & (pzsd_user.c.id != bestower.id)
                        & (pzsd_user.c.discord_snowflake != None)
                        & (pzsd_user.c.point_giver == True)
                    )
                    result = await session.execute(
                        insert(ledger).from_select(
                            ["bestower", "recipient", "points"], users
                        )
                    )
                    logger.info(
                        "Added %s point transactions to ledger", result.rowcount
                    )

            title = "Point transaction"
            color = Colors.white.value
        else:
            logger.info(
                "%s attempted to give themselves %s points. Very naughty.",
                bestower.name,
                pretty_point_amount,
            )
            title = "Self point violation!"
            color = Colors.red.value

        embed = discord.Embed(
            title=title,
            description=f"[Jump to original message]({message.jump_url})",
            colour=color,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Bestower", value=bestower.name, inline=True)
        embed.add_field(
            name="Recipient",
            value=recipient.name if not is_to_everyone else EVERYONE_KEYWORD,
            inline=True,
        )
        embed.add_field(name="Point amount", value=pretty_point_amount, inline=True)
        message_content = message.content
        if len(message_content) > 80:
            message_content = message_content[:80] + "\N{HORIZONTAL ELLIPSIS}"
        embed.add_field(name="Content of message:", value=message_content, inline=False)

        points_log_channel = self.bot.get_channel(Channels.points_log)
        await points_log_channel.send(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(Points(bot))
