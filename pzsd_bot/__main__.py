import logging
import os
import re
from datetime import datetime

import discord
from discord import Intents
from dotenv import load_dotenv
from sqlalchemy import insert, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import create_async_engine

from pzsd_bot.model import ledger, pzsd_user

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = os.environ["GUILD_ID"]

connection_str = "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
    os.getenv("PGUSER", "postgres"),
    os.getenv("PGPASSWORD", "password"),
    os.getenv("PGHOST", "localhost"),
    os.getenv("PGPORT", "5432"),
    os.getenv("PGDATABASE", "pzsd"),
)
engine = create_async_engine(connection_str)

logger = logging.getLogger("pzsd")
logger.setLevel(LOG_LEVEL)
handler = logging.FileHandler(filename="pzsd_bot.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

bot = discord.Bot(intents=Intents.all())

point_pattern = re.compile(
    r"(?:^| )([+-]?(?:\d+|\d{1,3}(?:,\d{3})*)) +points? (?:to|for) (?:(\w+)|<@(\d+)>)",
    re.IGNORECASE,
)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if match := point_pattern.search(message.content):
        point_amount = int(match[1].replace(",", ""))
        recipient_name = match[2]
        recipient_id = match[3]

        async with engine.connect() as conn:
            result = await conn.execute(
                select(pzsd_user).where(
                    pzsd_user.c.discord_snowflake == str(message.author.id)
                )
            )
            try:
                bestower = result.one()
            except NoResultFound:
                logger.info(
                    "User '%s' with snowflake '%s' tried to bestow points but wasn't in the user table",
                    message.author.name,
                    message.author.id,
                )
                return

            if recipient_name:
                result = await conn.execute(
                    select(pzsd_user).where(pzsd_user.c.name == recipient_name)
                )
            else:
                result = await conn.execute(
                    select(pzsd_user).where(
                        pzsd_user.c.discord_snowflake == recipient_id
                    )
                )
            try:
                recipient = result.one()
            except NoResultFound:
                logger.info(
                    "%s tried to bestow points to '%s' but they weren't in the user table",
                    bestower.name,
                    recipient_name or recipient_id,
                )
                return

        logger.info(
            f"{bestower.name} awarding {point_amount} point(s) to {recipient.name}"
        )

        async with engine.begin() as conn:
            await conn.execute(
                insert(ledger).values(
                    bestower=bestower.id, recipient=recipient.id, points=point_amount
                )
            )
            logger.info("Added point transaction to ledger")

        embed = discord.Embed(
            title="Point transaction",
            description=f"[Jump to original message]({message.jump_url})",
            colour=0xFFFFFF,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Bestower", value=bestower.name, inline=True)
        embed.add_field(name="Recipient", value=recipient.name, inline=True)
        embed.add_field(name="Point amount", value=str(point_amount), inline=True)
        message_content = message.content
        if len(message_content) > 80:
            message_content = message_content[:80] + "..."
        embed.add_field(name="Content of message:", value=message_content, inline=False)

        points_log_channel = bot.get_channel(int(os.environ["POINTS_LOG_CHANNEL"]))
        await points_log_channel.send(embed=embed)


@bot.slash_command(guild_ids=[GUILD_ID])
async def test(ctx):
    await ctx.respond("This was a test.")


bot.run(BOT_TOKEN)
