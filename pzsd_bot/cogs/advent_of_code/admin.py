import logging

from discord import ApplicationContext, Bot
from discord.ext.commands import Cog, slash_command
from pycord.multicog import subcommand

from pzsd_bot.settings import Guilds, Roles

logger = logging.getLogger(__name__)


class AOCAdmin(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @subcommand(group="aoc")
    @slash_command(
        name="subscribe", description="Subscribe to aoc puzzle notifications."
    )
    async def subscribe(self, ctx: ApplicationContext) -> None:
        logger.info("/subscribe invoked by %s", ctx.author.name)

        if ctx.author.get_role(Roles.advent_of_code) is not None:
            logger.info("%s already has aoc role, doing nothing", ctx.author.name)
            await ctx.respond("You are already subscribed.")
        else:
            guild = self.bot.get_guild(Guilds.pzsd)
            aoc_role = guild.get_role(Roles.advent_of_code)
            await ctx.author.add_roles(
                aoc_role, reason="Subscribed to aoc notifications"
            )
            logger.info("Added aoc role to %s", ctx.author.name)
            await ctx.respond(
                "🎄 You've been subscribed to Advent of Code puzzle notifications! 🎄"
            )

    @subcommand(group="aoc")
    @slash_command(
        name="unsubscribe", description="Unsubscribe from aoc puzzle notifications."
    )
    async def unsubscribe(self, ctx: ApplicationContext) -> None:
        logger.info("/unsubscribe invoked by %s", ctx.author.name)

        if ctx.author.get_role(Roles.advent_of_code) is None:
            logger.info("%s doesn't have aoc role, doing nothing", ctx.author.name)
            await ctx.respond("You already aren't subscribed.")
        else:
            guild = self.bot.get_guild(Guilds.pzsd)
            aoc_role = guild.get_role(Roles.advent_of_code)
            await ctx.author.remove_roles(
                aoc_role, reason="Unsubscribed from aoc notifications"
            )
            logger.info("Removed aoc role from %s", ctx.author.name)
            await ctx.respond(
                "You've been unsubscribed from Advent of Code puzzle notifications. :c"
            )


def setup(bot: Bot) -> None:
    bot.add_cog(AOCAdmin(bot))
