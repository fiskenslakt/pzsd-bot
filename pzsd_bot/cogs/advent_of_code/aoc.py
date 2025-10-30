import asyncio
import logging

import pendulum
from discord import Bot
from discord.ext.commands import Cog

from pzsd_bot.ext.scheduler import Scheduler
from pzsd_bot.settings import AOCSettings, Channels, Guilds, Roles

logger = logging.getLogger(__name__)

CURRENT_YEAR = pendulum.today().year


class AdventOfCode(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = Scheduler(__class__.__name__)

        asyncio.create_task(self.schedule_aoc_thread_posts())

    async def schedule_aoc_thread_posts(self) -> None:
        logger.info("Scheduling AoC thread posts")

        event_start = pendulum.datetime(
            CURRENT_YEAR,
            AOCSettings.event_start_month,
            AOCSettings.event_start_day,
            tz="America/New_York",
        )

        for offset in range(AOCSettings.days_in_event):
            dt = event_start.add(days=offset)
            if dt.is_future():
                self.scheduler.schedule(
                    run_at=dt,
                    task_id=f"aoc_thread_day_{dt.day}_{dt.year}",
                    coroutine=self.create_aoc_thread(dt.day),
                )

    async def create_aoc_thread(self, day: int) -> None:
        logger.info("Creating aoc thread for day %s", day)

        aoc_channel = self.bot.get_channel(Channels.advent_of_code)
        if aoc_channel is None:
            logger.error("advent-of-code channel is missing, unable to create thread")
            return

        guild = self.bot.get_guild(Guilds.pzsd)
        aoc_role = guild.get_role(Roles.advent_of_code)

        msg = await aoc_channel.send(f"Today's {aoc_role.mention} puzzle is live!")

        thread = await msg.create_thread(name=f"Day {day} {CURRENT_YEAR}")
        await thread.send(
            "You can discuss today's puzzle in this thread.\n"
            r"**All answers and hints must be spoiler tagged.** (eg. \|\| Invert the binary tree \|\|)"
        )


def setup(bot: Bot) -> None:
    if AOCSettings.aoc_event_active:
        bot.add_cog(AdventOfCode(bot))
