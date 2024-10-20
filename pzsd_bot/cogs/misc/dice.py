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

D20_FACES = {
    1: Emoji.d20_1,
    2: Emoji.d20_2,
    3: Emoji.d20_3,
    4: Emoji.d20_4,
    5: Emoji.d20_5,
    6: Emoji.d20_6,
    7: Emoji.d20_7,
    8: Emoji.d20_8,
    9: Emoji.d20_9,
    10: Emoji.d20_10,
    11: Emoji.d20_11,
    12: Emoji.d20_12,
    13: Emoji.d20_13,
    14: Emoji.d20_14,
    15: Emoji.d20_15,
    16: Emoji.d20_16,
    17: Emoji.d20_17,
    18: Emoji.d20_18,
    19: Emoji.d20_19,
    20: Emoji.d20_20,
}


class Dice(Cog):
    roll = SlashCommandGroup("roll", "Roll a die.")

    def __init__(self, bot: Bot):
        self.bot = bot

    @roll.command(description="Roll an n sided die.")
    @option("sides", description="How many sides the die should have.")
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
    @option(
        "rolls",
        description="How many dice to roll at once (default is 1).",
        min_value=1,
        max_value=10,
        required=False,
    )
    async def d20(self, ctx: ApplicationContext, rolls: int = 1) -> None:
        logger.info("%s invoked /roll d20 with rolls=%s", ctx.author.name, rolls)

        if rolls == 1:
            result = randint(1, 20)
            die_face = discord.File(DiceSettings.d20_images / f"d20_{result}.png")

            await ctx.send_response(file=die_face)
        else:
            results = [D20_FACES[randint(1, 20)] for _ in range(rolls)]
            await ctx.respond("".join(results))


def setup(bot: Bot) -> None:
    bot.add_cog(Dice(bot))
