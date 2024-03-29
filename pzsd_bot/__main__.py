import asyncio
import logging
import os
import re
from datetime import datetime

import discord
from discord import Intents
from dotenv import load_dotenv
from sqlalchemy import insert, select
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.functions import sum as sql_sum

from pzsd_bot.model import ledger, pzsd_user

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = os.environ["GUILD_ID"]
POINTS_LOG_CHANNEL = int(os.environ["POINTS_LOG_CHANNEL"])
POINT_MAX_VALUE = 9223372036854775807

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
handler = logging.FileHandler(filename="pzsd_bot.log", encoding="utf-8", mode="a")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

bot = discord.Bot(intents=Intents.all())

point_pattern = re.compile(
    r"(?:^| )(?P<point_amount>[+-]?(?:\d+|\d{1,3}(?:,\d{3})*)) "
    r"+points? (?:to|for) (?:(?P<recipient_name>\w+)|<@(?P<recipient_id>\d+)>)",
    re.IGNORECASE,
)


@bot.event
async def on_ready():
    print(f"Ready.")
    logger.info("Logged in as %s", bot.user)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if match := point_pattern.search(message.content):
        point_amount = int(match["point_amount"].replace(",", ""))
        recipient_name = match["recipient_name"]
        recipient_id = match["recipient_id"]

        async with engine.connect() as conn:
            result = await conn.execute(
                select(pzsd_user).where(
                    pzsd_user.c.discord_snowflake == str(message.author.id)
                )
            )
            try:
                bestower = result.one_or_none()
            except MultipleResultsFound:
                logger.error(
                    "Multiple users with snowflake '%s' found in user table",
                    message.author.id,
                )
                raise

            if bestower is None:
                logger.info(
                    "User '%s' with snowflake '%s' tried to bestow points but wasn't in the user table",
                    message.author.name,
                    message.author.id,
                )
                return

            if recipient_name:
                result = await conn.execute(
                    select(pzsd_user).where(pzsd_user.c.name == recipient_name.lower())
                )
            else:
                result = await conn.execute(
                    select(pzsd_user).where(
                        pzsd_user.c.discord_snowflake == recipient_id
                    )
                )
            try:
                recipient = result.one_or_none()
            except MultipleResultsFound:
                recipient_type = "name" if recipient_name else "snowflake"
                logger.error(
                    "Multiple users with %s '%s' found in user table",
                    recipient_type,
                    recipient_name or recipient_id,
                )
                raise

            if recipient is None:
                logger.info(
                    "%s tried to bestow points to '%s' but they weren't in the user table",
                    bestower.name,
                    recipient_name or recipient_id,
                )
                return

        excessive_point_violation = abs(point_amount) > POINT_MAX_VALUE
        if excessive_point_violation:
            logger.info(
                "%s tried to give %s more than the max allowed points (%s)",
                bestower.name,
                recipient.name,
                format(point_amount, ','),
            )
            return

        self_point_violation = bestower.id == recipient.id
        if self_point_violation:
            logger.info(
                "%s attempted to give themselves %s points. Very naughty.",
                bestower.name,
                point_amount,
            )
        else:
            logger.info(
                "%s awarding %s point(s) to %s",
                bestower.name,
                format(point_amount, ','),
                recipient.name,
            )

        if not self_point_violation:
            async with engine.begin() as conn:
                await conn.execute(
                    insert(ledger).values(
                        bestower=bestower.id,
                        recipient=recipient.id,
                        points=point_amount,
                    )
                )
                logger.info("Added point transaction to ledger")

        if self_point_violation:
            title = "Self point violation!"
            color = 0xFF0000
        else:
            title = "Point transaction"
            color = 0xFFFFFF
        embed = discord.Embed(
            title=title,
            description=f"[Jump to original message]({message.jump_url})",
            colour=color,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Bestower", value=bestower.name, inline=True)
        embed.add_field(name="Recipient", value=recipient.name, inline=True)
        embed.add_field(
            name="Point amount", value=format(point_amount, ","), inline=True
        )
        message_content = message.content
        if len(message_content) > 80:
            message_content = message_content[:80] + "..."
        embed.add_field(name="Content of message:", value=message_content, inline=False)

        points_log_channel = bot.get_channel(POINTS_LOG_CHANNEL)
        await points_log_channel.send(embed=embed)


@bot.slash_command(guild_ids=[GUILD_ID])
async def leaderboard(ctx):
    async with engine.connect() as conn:
        j = ledger.join(pzsd_user, pzsd_user.c.id == ledger.c.recipient, isouter=True)
        result = await conn.execute(
            select(pzsd_user.c.name, sql_sum(ledger.c.points))
            .select_from(j)
            .group_by(pzsd_user.c.id)
        )
        points = sorted(result.fetchall(), key=lambda r: r.sum, reverse=True)

    embed = discord.Embed(title="Points Leaderboard", colour=0xA8A434)
    for i, (name, point_total) in enumerate(points, 1):
        name = name.capitalize()
        point_total = int(point_total)  # avoid scientific notation
        embed.add_field(
            name=f"{i}. {name}", value=f"{point_total:,} points", inline=False
        )

    await ctx.respond(embed=embed)


async def run_bot():
    try:
        async with bot:
            await bot.start(BOT_TOKEN)
    finally:
        await engine.dispose()


try:
    asyncio.run(run_bot())
except KeyboardInterrupt:
    logger.info("Exiting.")
