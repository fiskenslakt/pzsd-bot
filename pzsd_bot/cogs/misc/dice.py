import logging
from random import randint

import discord
from discord import ApplicationContext, Bot
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog

from pzsd_bot.settings import DiceSettings, Emoji

logger = logging.getLogger(__name__)

D6_FACES = {
    1: Emoji.dice_1,
    2: Emoji.dice_2,
    3: Emoji.dice_3,
    4: Emoji.dice_4,
    5: Emoji.dice_5,
    6: Emoji.dice_6,
}


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

    @roll.command(description="Roll a 6 sided die.")
    @option(
        "rolls",
        description="How many dice to roll at once (default is 1).",
        min_value=1,
        max_value=10,
        required=False,
    )
    async def d6(self, ctx: ApplicationContext, rolls: int = 1) -> None:
        logger.info("%s invoked /roll d6 with rolls=%s", ctx.author.name, rolls)

        results = [D6_FACES[randint(1, 6)] for _ in range(rolls)]
        await ctx.respond("".join(results))

    @roll.command(description="Roll a 20 sided die.")
    async def d20(self, ctx: ApplicationContext) -> None:
        logger.info("%s invoked /roll d20", ctx.author.name)

        result = randint(1, 20)
        die_face = discord.File(DiceSettings.d20_images / f"{result}.png")

        await ctx.send_response(file=die_face)


def setup(bot: Bot) -> None:
    bot.add_cog(Dice(bot))
