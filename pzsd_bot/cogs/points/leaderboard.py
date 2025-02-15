import logging
import re
import uuid
from datetime import datetime, timedelta
from itertools import batched
from math import ceil
from typing import Iterable, Optional, Tuple

import pendulum
from discord import ApplicationContext, Bot, Embed
from discord.commands import SlashCommandGroup
from discord.ext.commands import Cog
from sqlalchemy import select
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.functions import sum as sql_sum

from pzsd_bot.db import Session
from pzsd_bot.ext.pagination import Paginator
from pzsd_bot.ext.scheduler import Scheduler
from pzsd_bot.model import ledger, pzsd_user
from pzsd_bot.settings import Channels, Colors, PointsSettings

logger = logging.getLogger(__name__)

LeaderboardField = Tuple[int, str, int]


class PointLeaderboard(Cog):
    leaderboard = SlashCommandGroup("leaderboard", "Display point leaderboards.")

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = Scheduler(__class__.__name__)

        # Schedule the initial weekly lb post
        # which can in turn schedule the next one
        self.scheduler.schedule(
            self.next_weekly_lb_post,
            f"weekly_leaderboard_post_{uuid.uuid4()}",
            self.weekly(None),
        )

    @property
    def next_weekly_lb_post(self):
        now = pendulum.now("America/New_York")
        if now.weekday() == pendulum.FRIDAY and now.hour < 16:
            friday_at_4pm = now.at(16)
        else:
            friday_at_4pm = now.next(pendulum.FRIDAY).at(16)

        return friday_at_4pm

    def cog_unload(self) -> None:
        self.scheduler.cancel_all()

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
    async def weekly(self, ctx: ApplicationContext | None) -> None:
        if ctx is not None:
            logger.info("`/leaderboard weekly` invoked by %s", ctx.author.name)
        else:
            logger.info("`/leaderboard weekly` invoked automatically by scheduler")

        last_week = datetime.now() - timedelta(days=7)
        leaderboard = await self.fetch_leaderboard(ledger.c.created_at > last_week)
        description = f"Points awarded after <t:{int(last_week.timestamp())}:f>"

        pages = []
        for lb_chunk in leaderboard:
            embed = self.make_leaderboard_embed(
                "Weekly Points Leaderboard", lb_chunk, description=description
            )
            pages.append(embed)

        if pages:
            paginator = Paginator(
                pages=pages,
                timeout=None,
                author_check=False,
                use_default_buttons=False,
                custom_buttons=PointsSettings.page_buttons,
            )
        else:
            paginator = None

        if ctx is not None:
            if paginator is not None:
                await paginator.respond(ctx.interaction)
            else:
                ctx.respond("No points have been bestowed in the last 7 days!")
        else:
            points_lounge_channel = self.bot.get_channel(Channels.points_lounge)
            if points_lounge_channel is None:
                logger.error(
                    "points-lounge channel is missing, unable to post weekly leaderboard."
                )
            elif paginator is not None:
                await paginator.channel_send(points_lounge_channel)
            else:
                await points_lounge_channel.send(
                    "No points have been bestowed in the last 7 days!"
                )

            # reschedule task for next friday at 4pm ET
            self.scheduler.schedule(
                self.next_weekly_lb_post,
                f"weekly_leaderboard_post_{uuid.uuid4()}",
                self.weekly(None),
            )

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
            timeout=None,
            author_check=False,
            use_default_buttons=False,
            custom_buttons=PointsSettings.page_buttons,
        )

        await paginator.respond(ctx.interaction)


def setup(bot: Bot) -> None:
    bot.add_cog(PointLeaderboard(bot))
