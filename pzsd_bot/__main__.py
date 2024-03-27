import logging
import os
from pathlib import Path

import discord
import yaml
from dotenv import load_dotenv

config_path = Path(__file__).parent / "config.yml"
if config_path.exists():
    with config_path.open() as f:
        config = yaml.safe_load(f)
else:
    config = {}

LOG_LEVEL = config.get("LOG_LEVEL", "INFO")

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
GUILD_ID = os.environ["GUILD_ID"]

logger = logging.getLogger("pzsd")
logger.setLevel(LOG_LEVEL)
handler = logging.FileHandler(filename="pzsd_bot.log", encoding="utf-8", mode="w")
handler.setFormatter(
    logging.Formatter("%(asctime)s:%(levelname)s:%(name)s: %(message)s")
)
logger.addHandler(handler)

bot = discord.Bot()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return


@bot.slash_command(guild_ids=[GUILD_ID])
async def test(ctx):
    await ctx.respond("This was a test.")


bot.run(BOT_TOKEN)
