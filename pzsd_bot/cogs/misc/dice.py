import logging
import re
from datetime import datetime
from random import randint

import discord
from discord import ApplicationContext, Bot, Message
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog
from sqlalchemy import insert, select

from pzsd_bot.db import Session
from pzsd_bot.model import ledger, pzsd_user
from pzsd_bot.settings import Colors, DiceSettings, Emoji, POINT_MAX_VALUE, POINT_MIN_VALUE

logger = logging.getLogger(__name__)


class Dice(Cog):
    roll = SlashCommandGroup("roll", "Roll a die.")

    def __init__(self, bot: Bot):
        self.bot = bot
        
    # Message command handler
    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        # Ignore messages from bots to prevent loops
        if message.author.bot:
            return
            
        # Check if message is a reply to another message
        is_reply = message.reference is not None
        
        # Parse message content for dice commands
        content = message.content.lower().strip()
        
        # Handle d6 command
        if re.match(r'^roll d6( \d+)?$', content):
            # Extract number of rolls if specified
            match = re.search(r'(\d+)', content)
            rolls = int(match.group(1)) if match else 1
            
            # Limit rolls to 1-10
            rolls = max(1, min(10, rolls))
            
            logger.info("%s used message command roll d6 with rolls=%s", message.author.name, rolls)
            results = [Emoji.get_d6(randint(1, 6)) for _ in range(rolls)]
            await message.reply("".join(results))
            
        # Handle d20 command
        elif re.match(r'^roll d20( \d+)?$', content):
            # Extract number of rolls if specified
            match = re.search(r'(\d+)', content)
            rolls = int(match.group(1)) if match else 1
            
            # Limit rolls to 1-10
            rolls = max(1, min(10, rolls))
            
            logger.info("%s used message command roll d20 with rolls=%s", message.author.name, rolls)
            
            if rolls == 1:
                result = randint(1, 20)
                die_face = discord.File(DiceSettings.d20_images / f"d20_{result}.png")
                await message.reply(file=die_face)
            else:
                results = [Emoji.get_d20(randint(1, 20)) for _ in range(rolls)]
                await message.reply("".join(results))
                
        # Handle dn command (n-sided die)
        elif re.match(r'^roll d\d+$', content):
            # Extract number of sides
            match = re.search(r'd(\d+)', content)
            if match:
                sides = int(match.group(1))
                logger.info("%s used message command roll d%s", message.author.name, sides)
                
                if sides > 0:
                    result = randint(1, sides)
                    await message.reply(f"The {sides} sided die landed on {result}")
                else:
                    await message.reply(f"The {sides} sided die landed on nothing because that makes no sense.")
                    
        # Handle reward command
        elif is_reply and re.match(r'^roll reward (\d+)$', content):
            # This command requires a reply to work
            match = re.search(r'(\d+)', content)
            if not match:
                return
                
            number = int(match.group(1))
            # Limit to 1-10 dice
            number = max(1, min(10, number))
            
            # Get the user being replied to
            if message.reference.resolved is None:
                await message.reply("Could not find the message you're replying to.")
                return
                
            user = message.reference.resolved.author
            
            # Don't allow rewarding bots
            if user.bot:
                await message.reply("You cannot reward points to bots.")
                return
                
            logger.info("%s used message command roll reward with number=%s for user %s",
                       message.author.name, number, user.name)
            
            # Get the recipient ID
            recipient_id = str(user.id)
                
            # Roll the dice
            results = []
            total_points = 0
            for _ in range(number):
                roll_result = randint(1, 6)
                total_points += roll_result
                results.append(Emoji.get_d6(roll_result))
                
            # Get the bestower (command user)
            async with Session.begin() as session:
                bestower_result = await session.execute(
                    select(pzsd_user).where(
                        pzsd_user.c.discord_snowflake == str(message.author.id)
                    )
                )
                bestower = bestower_result.one_or_none()
                
                if bestower is None:
                    await message.reply("You don't have permission to award points.")
                    return
                    
                if not bestower.is_active or not bestower.point_giver:
                    await message.reply("You don't have permission to award points.")
                    return
                    
                # Get the recipient
                recipient_result = await session.execute(
                    select(pzsd_user).where(
                        pzsd_user.c.discord_snowflake == recipient_id
                    )
                )
                recipient = recipient_result.one_or_none()
                
                if recipient is None:
                    await message.reply("The selected user is not registered in the system.")
                    return
                    
                if not recipient.is_active:
                    await message.reply("The selected user is not active in the system.")
                    return
                    
                # Check for self-point violation
                if bestower.id == recipient.id:
                    await message.reply("You cannot award points to yourself.")
                    return
                    
                # Check for point limits
                if not POINT_MIN_VALUE <= total_points <= POINT_MAX_VALUE:
                    await message.reply(f"Point amount {total_points} is outside the allowed range.")
                    return
                    
                # Award the points
                await session.execute(
                    insert(ledger).values(
                        bestower=bestower.id,
                        recipient=recipient.id,
                        points=total_points,
                    )
                )
                
            # Create the response embed
            embed = discord.Embed(
                title="Dice Roll & Point Reward",
                description=f"{message.author.mention} rolled {number} dice for {user.mention}",
                colour=Colors.white.value,
                timestamp=datetime.now(),
            )
            embed.add_field(name="Dice Results", value="".join(results), inline=False)
            embed.add_field(name="Total Points", value=str(total_points), inline=True)
            embed.add_field(name="Awarded To", value=user.mention, inline=True)
            
            # Send the response
            await message.reply(embed=embed)

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

        results = [Emoji.get_d6(randint(1, 6)) for _ in range(rolls)]
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
            results = [Emoji.get_d20(randint(1, 20)) for _ in range(rolls)]
            await ctx.respond("".join(results))

    @roll.command(description="Roll dice and reward points to the user you're replying to.")
    @option(
        "number",
        description="How many d6 dice to roll (1-10).",
        min_value=1,
        max_value=10,
        required=True,
    )
    @option(
        "user",
        description="The user to reward points to.",
        required=True,
    )
    async def reward(self, ctx: ApplicationContext, number: int, user: discord.Member) -> None:
        logger.info("%s invoked /roll reward with number=%s for user %s", ctx.author.name, number, user.name)
        
        # Get the recipient ID
        recipient_id = str(user.id)
            
        # Roll the dice
        results = []
        total_points = 0
        for _ in range(number):
            roll_result = randint(1, 6)
            total_points += roll_result
            results.append(Emoji.get_d6(roll_result))
            
        # Get the bestower (command user)
        async with Session.begin() as session:
            bestower_result = await session.execute(
                select(pzsd_user).where(
                    pzsd_user.c.discord_snowflake == str(ctx.author.id)
                )
            )
            bestower = bestower_result.one_or_none()
            
            if bestower is None:
                await ctx.respond("You don't have permission to award points.", ephemeral=True)
                return
                
            if not bestower.is_active or not bestower.point_giver:
                await ctx.respond("You don't have permission to award points.", ephemeral=True)
                return
                
            # Get the recipient
            recipient_result = await session.execute(
                select(pzsd_user).where(
                    pzsd_user.c.discord_snowflake == recipient_id
                )
            )
            recipient = recipient_result.one_or_none()
            
            if recipient is None:
                await ctx.respond("The selected user is not registered in the system.", ephemeral=True)
                return
                
            if not recipient.is_active:
                await ctx.respond("The selected user is not active in the system.", ephemeral=True)
                return
                
            # Check for self-point violation
            if bestower.id == recipient.id:
                await ctx.respond("You cannot award points to yourself.", ephemeral=True)
                return
                
            # Check for point limits
            if not POINT_MIN_VALUE <= total_points <= POINT_MAX_VALUE:
                await ctx.respond(f"Point amount {total_points} is outside the allowed range.", ephemeral=True)
                return
                
            # Award the points
            await session.execute(
                insert(ledger).values(
                    bestower=bestower.id,
                    recipient=recipient.id,
                    points=total_points,
                )
            )
            
        # Create the response embed
        embed = discord.Embed(
            title="Dice Roll & Point Reward",
            description=f"{ctx.author.mention} rolled {number} dice for {user.mention}",
            colour=Colors.white.value,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Dice Results", value="".join(results), inline=False)
        embed.add_field(name="Total Points", value=str(total_points), inline=True)
        embed.add_field(name="Awarded To", value=user.mention, inline=True)
        
        # Send the response
        await ctx.respond(embed=embed)


def setup(bot: Bot) -> None:
    bot.add_cog(Dice(bot))
