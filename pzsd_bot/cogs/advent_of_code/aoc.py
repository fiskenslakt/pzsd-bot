import logging

import pendulum
from discord import ApplicationContext, Bot, default_permissions
from discord.ext.commands import Cog, slash_command
from pycord.multicog import subcommand

from pzsd_bot.ext.scheduler import Scheduler
from pzsd_bot.settings import AOCSettings, Channels, Guilds, Roles

logger = logging.getLogger(__name__)


class AdventOfCode(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = Scheduler(__class__.__name__)
        self.event_active = False

    @subcommand(group="aoc", independent=True)
    @slash_command(description="Set aoc event to active.")
    @default_permissions(administrator=True)
    async def activate_event(self, ctx: ApplicationContext) -> None:
        logger.info("/aoc activate_event invoked by %s", ctx.author.name)

        if self.event_active:
            logger.info("aoc event already active, doing nothing")
            await ctx.respond("aoc event is already active!")
            return

        await self.schedule_aoc_thread_posts()
        self.event_active = True

        await ctx.respond("Event activated", ephemeral=True)

    @subcommand(group="aoc", independent=True)
    @slash_command(description="Set aoc event to inactive.")
    @default_permissions(administrator=True)
    async def deactivate_event(self, ctx: ApplicationContext) -> None:
        logger.info("/aoc deactivate_event invoked by %s", ctx.author.name)

        if not self.event_active:
            logger.info("aoc event already inactive, doing nothing")
            await ctx.respond("aoc event is already inactive!")
            return

        self.scheduler.cancel_all()
        self.event_active = False

        await ctx.respond("Event deactivated", ephemeral=True)

    async def schedule_aoc_thread_posts(self) -> None:
        logger.info("Scheduling AoC thread posts")

        current_year = pendulum.today().year

        event_start = pendulum.datetime(
            current_year,
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

        current_year = pendulum.today().year

        aoc_channel = self.bot.get_channel(Channels.advent_of_code)
        if aoc_channel is None:
            logger.error("advent-of-code channel is missing, unable to create thread")
            return

        guild = self.bot.get_guild(Guilds.pzsd)
        aoc_role = guild.get_role(Roles.advent_of_code)

        msg = await aoc_channel.send(f"Today's {aoc_role.mention} puzzle is live!")

        thread = await msg.create_thread(name=f"Day {day} {current_year}")
        await thread.send(
            "You can discuss today's puzzle in this thread.\n"
            r"**All answers and hints must be spoiler tagged.** (eg. \|\| Invert the binary tree \|\|)"
        )


def setup(bot: Bot) -> None:
    bot.add_cog(AdventOfCode(bot))
