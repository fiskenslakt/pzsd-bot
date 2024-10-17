import logging
from random import randint

import discord
from discord import ApplicationContext, Bot
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog

from pzsd_bot.settings import DiceSettings

logger = logging.getLogger(__name__)


class Dice(Cog):
    roll = SlashCommandGroup("roll", "Roll a die.")

    def __init__(self, bot: Bot):
        self.bot = bot

    @roll.command(description="Roll an n sided die.")
    @option("sides", description="How many sides the die should have (default is 6).")
    async def dn(self, ctx: ApplicationContext, sides: int) -> None:
        logger.info("%s invoked /roll dn with sides=%s", ctx.author.name, sides)

        if sides > 0:
            result = randint(1, sides)
            await ctx.respond(f"The {sides} sided die landed on {result}")
        else:
            await ctx.respond(
                f"The {sides} sided die landed on nothing because that makes no sense."
            )

    @roll.command(description="Roll a 20 sided die.")
    async def d20(self, ctx: ApplicationContext) -> None:
        logger.info("%s invoked /roll d20", ctx.author.name)

        result = randint(1, 20)
        die_face = discord.File(DiceSettings.d20_images / f"{result}.png")

        await ctx.send_response(file=die_face)


def setup(bot: Bot) -> None:
    bot.add_cog(Dice(bot))
