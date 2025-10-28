import asyncio
import logging

import discord
from discord import Intents

from pzsd_bot.client import Client
from pzsd_bot.db import engine
from pzsd_bot.settings import Bot

logger = logging.getLogger(__name__)

bot = discord.Bot(intents=Intents.all())
bot.client = Client()


@bot.event
async def on_ready():
    await bot.client.start()
    logger.info("Logged in as %s", bot.user)


async def run_bot():
    try:
        async with bot:
            bot.load_extensions("pzsd_bot.cogs", recursive=True)
            await bot.start(Bot.token)
    finally:
        await engine.dispose()
        await bot.client.close()


try:
    asyncio.run(run_bot())
except KeyboardInterrupt:
    logger.info("Exiting.")
