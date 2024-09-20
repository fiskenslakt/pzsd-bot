import logging
import re
from datetime import datetime, timedelta
from enum import Enum, auto
from itertools import batched
from math import ceil
from typing import Iterable, Optional, Tuple

import discord
from discord import ApplicationContext, Bot, Embed, Message, default_permissions
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog, slash_command
from discord.ext.pages import Paginator, PaginatorButton
from sqlalchemy import insert, select, text, update
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.functions import sum as sql_sum

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


class NameState(Enum):
    VALID_NAME = auto()
    INVALID_NAME = auto()
    DISALLOWED_NAME = auto()


class Points(Cog):
    leaderboard = SlashCommandGroup("leaderboard", "Display point leaderboards.")

    def __init__(self, bot: Bot):
        self.bot = bot

    @property
    def page_buttons(self) -> list[PaginatorButton]:
        return [
            PaginatorButton("first", label="<<", style=discord.ButtonStyle.blurple),
            PaginatorButton("prev", label="←", style=discord.ButtonStyle.blurple),
            PaginatorButton(
                "page_indicator", style=discord.ButtonStyle.gray, disabled=True
            ),
            PaginatorButton("next", label="→", style=discord.ButtonStyle.blurple),
            PaginatorButton("last", label=">>", style=discord.ButtonStyle.blurple),
        ]

    def validate_name(self, name: str) -> Enum:
        if name in PointsSettings.disallowed_names:
            return NameState.DISALLOWED_NAME
        elif not PointsSettings.valid_name_pattern.fullmatch(name):
            return NameState.INVALID_NAME
        return NameState.VALID_NAME

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

    async def fetch_leaderboard(
        self, *args: list[BinaryExpression], paginate: bool = True, page_size: int = 10
    ) -> Iterable[LeaderboardField] | Iterable[tuple[LeaderboardField, ...]]:
        logger.info(
            "Fetching leaderboard with paginate=%s and page_size=%s",
            paginate,
            page_size,
        )

        async with Session.begin() as session:
            j = ledger.join(
                pzsd_user, pzsd_user.c.id == ledger.c.recipient, isouter=True
            )
            result = await session.execute(
                select(pzsd_user.c.name, sql_sum(ledger.c.points))
                .select_from(j)
                .where(pzsd_user.c.is_active == True)
                .where(*args)
                .group_by(pzsd_user.c.id)
            )
            sorted_points = sorted(result.fetchall(), key=lambda r: r.sum, reverse=True)

        logger.info("Leaderboard length is %s", len(sorted_points))

        leaderboard = (
            (rank, name, points) for rank, (name, points) in enumerate(sorted_points, 1)
        )

        if paginate:
            leaderboard = batched(leaderboard, page_size)
            logger.info(
                "Leaderboard has %s pages", ceil(len(sorted_points) / page_size)
            )

        return leaderboard

    def make_leaderboard_embed(
        self,
        title: str,
        leaderboard: Iterable[LeaderboardField],
        description: Optional[str] = None,
    ) -> Embed:
        embed = Embed(title=title, description=description, colour=Colors.yellowy.value)
        for rank, name, point_total in leaderboard:
            # title case name by only capitalizing
            # words separated by hyphen or space
            name = "".join(map(str.capitalize, re.split(r"( |-)", name)))
            point_total = int(point_total)  # avoid scientific notation
            embed.add_field(
                name=f"{rank}. {name}", value=f"{point_total:,} points", inline=False
            )

        return embed

    @leaderboard.command(description="Display points awarded in the last 7 days.")
    async def weekly(self, ctx: ApplicationContext) -> None:
        logger.info("`/leaderboard weekly` invoked by %s", ctx.author.name)

        last_week = datetime.now() - timedelta(days=7)
        leaderboard = await self.fetch_leaderboard(ledger.c.created_at > last_week)
        description = f"Points awarded after <t:{int(last_week.timestamp())}:f>"

        pages = []
        for lb_chunk in leaderboard:
            embed = self.make_leaderboard_embed(
                "Weekly Points Leaderboard", lb_chunk, description=description
            )
            pages.append(embed)

        paginator = Paginator(
            pages=pages,
            disable_on_timeout=False,
            author_check=False,
            use_default_buttons=False,
            custom_buttons=self.page_buttons,
        )

        await paginator.respond(ctx.interaction)

    @leaderboard.command(
        description="Display total points awarded from the beginning of time."
    )
    async def total(self, ctx: ApplicationContext) -> None:
        logger.info("`/leaderboard total` invoked by %s", ctx.author.name)

        leaderboard = await self.fetch_leaderboard()

        pages = []
        for lb_chunk in leaderboard:
            embed = self.make_leaderboard_embed("All Time Points Leaderboard", lb_chunk)
            pages.append(embed)

        paginator = Paginator(
            pages=pages,
            disable_on_timeout=False,
            author_check=False,
            use_default_buttons=False,
            custom_buttons=self.page_buttons,
        )

        await paginator.respond(ctx.interaction)

    @slash_command(description="Add new name that can be bestowed points.")
    @option("name", description="The exact name to use when bestowing points.")
    @option("snowflake", description="Their discord ID if applicable.", required=False)
    @option(
        "point_giver",
        description="Determines if this user can bestow points.",
        default=False,
        choices=[True, False],
    )
    @default_permissions(administrator=True)
    async def register(
        self, ctx: ApplicationContext, name: str, snowflake: str, point_giver: bool
    ) -> None:
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /register with name='%s' snowflake=%s point_giver=%s",
            ctx.author.name,
            name,
            snowflake,
            point_giver,
        )

        name_state = self.validate_name(name)

        if name_state is NameState.DISALLOWED_NAME:
            logger.info("The name '%s' is not allowed, doing nothing", name)
            await ctx.respond(f"You cannot register the name '{name}'!")
            return
        elif name_state is NameState.INVALID_NAME:
            logger.info("'%s' is an invalid name, doing nothing", name)
            await ctx.respond(f"{name} is an invalid name, try something else.")
            return

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == name)
            )

        user_to_add = result.one_or_none()
        if user_to_add is not None:
            if user_to_add.is_active:
                logger.info("User '%s' already exists, doing nothing", name)
                await ctx.respond(f"'{name}' already exists!")
                return
            else:
                logger.info("User '%s' exists but is inactive", name)
                async with Session.begin() as session:
                    await session.execute(
                        update(pzsd_user)
                        .where(pzsd_user.c.name == name)
                        .values(
                            is_active=True,
                            discord_snowflake=snowflake,
                            point_giver=point_giver,
                        )
                    )
                logger.info("Reactivated user '%s' in user table", name)
                await ctx.respond(f"Reactivated user with name {name}")
        else:
            async with Session.begin() as session:
                await session.execute(
                    insert(pzsd_user).values(
                        name=name,
                        discord_snowflake=snowflake,
                        point_giver=point_giver,
                    )
                )
            logger.info("Added user '%s' to user table", name)
            await ctx.respond(f"Added user with name {name}")

    @slash_command(
        description="Remove name from being able to be bestowed points.",
    )
    @option("name", description="The exact name in the user table")
    @default_permissions(administrator=True)
    async def unregister(self, ctx: ApplicationContext, name: str) -> None:
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /unregister with name=%s",
            ctx.author.name,
            name,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == name)
            )

        user_to_del = result.one_or_none()
        if user_to_del is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", name)
            await ctx.respond(f"User '{name}' already doesn't exist!")
            return
        elif not user_to_del.is_active:
            logger.info("User '%s' is currently inactive, doing nothing", name)
            await ctx.respond(f"User '{name}' is already inactive!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.name == name)
                .values(is_active=False)
            )

        logger.info("Deactivated user '%s' in user table", name)
        await ctx.respond(f"Deactivated user with name {name}")

    @slash_command(description="Show user table.")
    @default_permissions(administrator=True)
    async def users(self, ctx: ApplicationContext) -> None:
        logger.info("%s invoked /users", ctx.author.name)

        async with Session.begin() as session:
            users = await session.execute(select(pzsd_user))

        pages = []

        for page in batched(sorted(users, key=lambda u: u.name), 5):
            embed = Embed(title="User List")
            for user in page:
                value = "Snowflake: {}\nActive: {}\nPoint Giver: {}\nCreated: <t:{}:f>"
                value = value.format(
                    user.discord_snowflake or "N/A",
                    user.is_active,
                    user.point_giver,
                    int(user.created_at.timestamp()),
                )
                embed.add_field(name=user.name, value=value, inline=False)
            pages.append(embed)

        paginator = Paginator(
            pages=pages,
            disable_on_timeout=False,
            author_check=True,
            use_default_buttons=False,
            custom_buttons=self.page_buttons,
        )

        await paginator.respond(ctx.interaction)

    @slash_command(description="Rename user in user table.")
    @option("user", description="User in user table to rename.")
    @option("name", description="Name to give user.")
    @default_permissions(administrator=True)
    async def rename(self, ctx: ApplicationContext, user: str, name: str) -> None:
        user = user.lower().strip("\"' \n\t")
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /rename with user='%s' name='%s'",
            ctx.author.name,
            user,
            name,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_rename = result.one_or_none()
        if user_to_rename is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return

        name_state = self.validate_name(name)

        if name_state is NameState.DISALLOWED_NAME:
            logger.info("The name '%s' is not allowed, doing nothing", name)
            await ctx.respond(f"You cannot use the name '{name}'!")
            return
        elif name_state is NameState.INVALID_NAME:
            logger.info("'%s' is an invalid name, doing nothing", name)
            await ctx.respond(f"{name} is an invalid name, try something else.")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_rename.id)
                .values(name=name)
            )

        logger.info("Renamed user '%s' to '%s'", user, name)
        await ctx.respond(f"Renamed {user} to {name}")

    @slash_command(description="Endow user with point giving abilities.")
    @option("user", description="User in user table to endow.")
    @default_permissions(administrator=True)
    async def endow(self, ctx: ApplicationContext, user: str) -> None:
        user = user.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /endow with user='%s'",
            ctx.author.name,
            user,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_endow = result.one_or_none()
        if user_to_endow is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return
        elif user_to_endow.point_giver:
            logger.info("User '%s' is already a point giver, doing nothing", user)
            await ctx.respond(f"{user} can already give points!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_endow.id)
                .values(point_giver=True)
            )

        logger.info("Endowed user '%s' with point giving abilities", user)
        await ctx.respond(f"Endowed {user} with point giving abilities.")

    @slash_command(description="Remove user's ability to give points.")
    @option("user", description="User in user table to disendow.")
    @default_permissions(administrator=True)
    async def disendow(self, ctx: ApplicationContext, user: str) -> None:
        user = user.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /disendow with user='%s'",
            ctx.author.name,
            user,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_disendow = result.one_or_none()
        if user_to_disendow is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return
        elif not user_to_disendow.point_giver:
            logger.info("User '%s' isn't a point giver, doing nothing", user)
            await ctx.respond(f"{user} isn't a point giver already!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_disendow.id)
                .values(point_giver=False)
            )

        logger.info("Removed ability to give points from user '%s'", user)
        await ctx.respond(f"Disendowed {user}")


def setup(bot: Bot) -> None:
    bot.add_cog(Points(bot))
