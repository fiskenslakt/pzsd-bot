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
async def leaderboard(ctx):
    points = {}

    async with engine.connect() as conn:
        result = await conn.execute(select(pzsd_user))
        for row in result.fetchall():
            points[row.id] = {"name": row.name, "point_total": 0}

        result = await conn.execute(select(ledger))
        for row in result:
            points[row.recipient]["point_total"] += row.points

    embed = discord.Embed(title="Points Leaderboard", colour=0xA8A434)
    for i, user in enumerate(
        sorted(points.values(), key=lambda d: d["point_total"], reverse=True), 1
    ):
        name = user["name"].capitalize()
        point_total = user["point_total"]
        embed.add_field(
            name=f"{i}. {name}", value=f"{point_total:,} points", inline=False
        )

    await ctx.respond(embed=embed)


async def run_bot():
    try:
        await bot.start(BOT_TOKEN)
    finally:
        await engine.dispose()


try:
    asyncio.run(run_bot())
except KeyboardInterrupt:
    print("Exiting...")
