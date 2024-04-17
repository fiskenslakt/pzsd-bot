import asyncio
import logging
import os
import re
from datetime import datetime
from enum import Enum

import discord
from discord import Intents, default_permissions
from discord.commands import option
from dotenv import load_dotenv
from sqlalchemy import insert, select, text, update
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql.functions import sum as sql_sum

from pzsd_bot.model import ledger, pzsd_user

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
BOT_TOKEN = os.environ["BOT_TOKEN"]
POINTS_LOG_CHANNEL = int(os.environ["POINTS_LOG_CHANNEL"])
POINT_MAX_VALUE = 9223372036854775807
POINT_MIN_VALUE = ~POINT_MAX_VALUE

connection_str = "postgresql+asyncpg://{}:{}@{}:{}/{}".format(
    os.getenv("PGUSER", "postgres"),
    os.getenv("PGPASSWORD", "password"),
    os.getenv("PGHOST", "localhost"),
    os.getenv("PGPORT", "5432"),
    os.getenv("PGDATABASE", "pzsd"),
)
engine = create_async_engine(connection_str)

logger = logging.getLogger("discord")
logger.setLevel(LOG_LEVEL)
handler = logging.FileHandler(filename="pzsd_bot.log", encoding="utf-8", mode="a")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

bot = discord.Bot(intents=Intents.all())

point_pattern = re.compile(
    r"(?:^| )(?P<point_amount>[+-]?(?:\d+|\d{1,3}(?:,\d{3})*)) "
    r"+points? (?:to|for) (?:(?P<recipient_name>[\w-]+)|<@(?P<recipient_id>\d+)>)",
    re.IGNORECASE,
)


class Color(Enum):
    WHITE = 0xFFFFFF
    RED = 0xFF0000
    YELLOWY = 0xA8A434


@bot.event
async def on_ready():
    print("Ready.")
    logger.info("Logged in as %s", bot.user)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if match := point_pattern.search(message.content):
        point_amount = int(match["point_amount"].replace(",", ""))
        pretty_point_amount = format(point_amount, ",")
        recipient_name = match["recipient_name"]
        recipient_id = match["recipient_id"]

        async with engine.connect() as conn:
            result = await conn.execute(
                select(pzsd_user).where(
                    (pzsd_user.c.discord_snowflake == str(message.author.id))
                    & (pzsd_user.c.is_active == True)
                )
            )

            bestower = result.one_or_none()

            if bestower is None:
                logger.info(
                    "User '%s' with snowflake '%s' tried to bestow points but wasn't in the user table",
                    message.author.name,
                    message.author.id,
                )
                return

            is_to_everyone = False
            if recipient_name is None:
                condition = pzsd_user.c.discord_snowflake == recipient_id
            elif recipient_name.lower() == "everyone":
                is_to_everyone = True
            else:
                condition = pzsd_user.c.name == recipient_name.lower()

            if not is_to_everyone:
                result = await conn.execute(
                    select(pzsd_user).where(condition & pzsd_user.c.is_active == True)
                )

                recipient = result.one_or_none()

                if recipient is None:
                    logger.info(
                        "%s tried to bestow points to '%s' but they weren't in the user table",
                        bestower.name,
                        recipient_name or recipient_id,
                    )
                    return

        excessive_point_violation = (
            not POINT_MIN_VALUE <= point_amount <= POINT_MAX_VALUE
        )
        if excessive_point_violation:
            logger.info(
                "%s tried to give %s more than the max allowed points (%s)",
                bestower.name,
                recipient.name if not is_to_everyone else "everyone",
                pretty_point_amount,
            )
            return

        self_point_violation = is_to_everyone is False and bestower.id == recipient.id
        if not self_point_violation:
            logger.info(
                "%s awarding %s point(s) to %s",
                bestower.name,
                pretty_point_amount,
                recipient.name if not is_to_everyone else "everyone",
            )
            if not is_to_everyone:
                async with engine.begin() as conn:
                    await conn.execute(
                        insert(ledger).values(
                            bestower=bestower.id,
                            recipient=recipient.id,
                            points=point_amount,
                        )
                    )
                logger.info("Added point transaction to ledger")
            else:
                async with engine.begin() as conn:
                    users = select(
                        text(f"'{bestower.id}'"),
                        pzsd_user.c.id,
                        text(str(point_amount)),
                    ).where(
                        (pzsd_user.c.is_active == True)
                        & (pzsd_user.c.id != bestower.id)
                    )
                    result = await conn.execute(
                        insert(ledger).from_select(
                            ["bestower", "recipient", "points"], users
                        )
                    )
                    logger.info(
                        "Added %s point transactions to ledger", result.rowcount
                    )

            title = "Point transaction"
            color = Color.WHITE.value
        else:
            logger.info(
                "%s attempted to give themselves %s points. Very naughty.",
                bestower.name,
                pretty_point_amount,
            )
            title = "Self point violation!"
            color = Color.RED.value

        embed = discord.Embed(
            title=title,
            description=f"[Jump to original message]({message.jump_url})",
            colour=color,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Bestower", value=bestower.name, inline=True)
        embed.add_field(
            name="Recipient",
            value=recipient.name if not is_to_everyone else "everyone",
            inline=True,
        )
        embed.add_field(name="Point amount", value=pretty_point_amount, inline=True)
        message_content = message.content
        if len(message_content) > 80:
            message_content = message_content[:80] + "\N{HORIZONTAL ELLIPSIS}"
        embed.add_field(name="Content of message:", value=message_content, inline=False)

        points_log_channel = bot.get_channel(POINTS_LOG_CHANNEL)
        await points_log_channel.send(embed=embed)


@bot.slash_command(description="Display everyone's points in descending order.")
async def leaderboard(ctx):
    async with engine.connect() as conn:
        j = ledger.join(pzsd_user, pzsd_user.c.id == ledger.c.recipient, isouter=True)
        result = await conn.execute(
            select(pzsd_user.c.name, sql_sum(ledger.c.points))
            .select_from(j)
            .where(pzsd_user.c.is_active == True)
            .group_by(pzsd_user.c.id)
        )
        points = sorted(result.fetchall(), key=lambda r: r.sum, reverse=True)

    embed = discord.Embed(title="Points Leaderboard", colour=Color.YELLOWY.value)
    for i, (name, point_total) in enumerate(points, 1):
        name = name.capitalize()
        point_total = int(point_total)  # avoid scientific notation
        embed.add_field(
            name=f"{i}. {name}", value=f"{point_total:,} points", inline=False
        )

    await ctx.respond(embed=embed)


@bot.slash_command(description="Add new name that can be bestowed points.")
@option("name", description="The exact name to use when bestowing points.")
@option("snowflake", description="Their discord ID if applicable.", required=False)
@default_permissions(administrator=True)
async def register(ctx, name, snowflake):
    name = name.lower()

    logger.info(
        "%s invoked /register with name=%s and snowflake=%s",
        ctx.author.name,
        name,
        snowflake,
    )

    async with engine.connect() as conn:
        result = await conn.execute(select(pzsd_user).where(pzsd_user.c.name == name))

    user_to_add = result.one_or_none()
    if user_to_add is not None:
        if user_to_add.is_active:
            logger.info("User '%s' already exists, doing nothing", name)
            await ctx.respond(f"'{name}' already exists!")
            return
        else:
            logger.info("User '%s' exists but is inactive", name)
            async with engine.begin() as conn:
                await conn.execute(
                    update(pzsd_user)
                    .where(pzsd_user.c.name == name)
                    .values(is_active=True, discord_snowflake=snowflake)
                )
            logger.info("Reactivated user '%s' in user table", name)
            await ctx.respond(f"Reactivated user with name {name}")
    else:
        async with engine.begin() as conn:
            await conn.execute(
                insert(pzsd_user).values(
                    name=name,
                    discord_snowflake=snowflake,
                )
            )
        logger.info("Added user '%s' to user table", name)
        await ctx.respond(f"Added user with name {name}")


@bot.slash_command(
    description="Remove name from being able to be bestowed points.",
)
@option("name", description="The exact name in the user table")
@default_permissions(administrator=True)
async def unregister(ctx, name):
    name = name.lower()

    logger.info(
        "%s invoked /unregister with name=%s",
        ctx.author.name,
        name,
    )

    async with engine.connect() as conn:
        result = await conn.execute(select(pzsd_user).where(pzsd_user.c.name == name))

    user_to_del = result.one_or_none()
    if user_to_del is None:
        logger.info("User '%s' doesn't exist in user table, doing nothing", name)
        await ctx.respond(f"User '{name}' already doesn't exist!")
        return
    elif not user_to_del.is_active:
        logger.info("User '%s' is currently inactive, doing nothing", name)
        await ctx.respond(f"User '{name}' is already inactive!")
        return

    async with engine.begin() as conn:
        await conn.execute(
            update(pzsd_user).where(pzsd_user.c.name == name).values(is_active=False)
        )

    logger.info("Deactivated user '%s' in user table", name)
    await ctx.respond(f"Deactivated user with name {name}")


@bot.slash_command(description="Show user table.")
@default_permissions(administrator=True)
async def users(ctx):
    logger.debug("%s invoked /users", ctx.author.name)

    async with engine.connect() as conn:
        result = await conn.execute(
            select(pzsd_user).where(pzsd_user.c.is_active == True)
        )

    embed = discord.Embed()

    for row in result:
        embed.add_field(name=row.name, value=row.discord_snowflake or "N/A")

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
