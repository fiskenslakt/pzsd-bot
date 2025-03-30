import logging
from typing import List

from discord import (
    ApplicationContext,
    Bot,
    Embed,
    Member,
    OptionChoice,
    default_permissions,
)
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog, slash_command
from discord.ext.pages import Paginator
from pendulum import duration
from sqlalchemy import delete, false, select, true, update
from sqlalchemy.engine import Row
from sqlalchemy.sql.elements import BinaryExpression

from pzsd_bot.db import Session
from pzsd_bot.model import pzsd_user, reminder
from pzsd_bot.settings import Roles
from pzsd_bot.ui.buttons import get_page_buttons

logger = logging.getLogger(__name__)

# If you're somehow not in one
# of these timezones, too bad.
TIMEZONE_CHOICES = [
    OptionChoice(name="UTC", value="UTC"),
    OptionChoice(name="New York (EST/EDT)", value="America/New_York"),
    OptionChoice(name="Chicago (CST/CDT)", value="America/Chicago"),
    OptionChoice(name="Denver (MST/MDT)", value="America/Denver"),
    OptionChoice(name="Los Angeles (PST/PDT)", value="America/Los_Angeles"),
    OptionChoice(name="Phoenix (MST, No DST)", value="America/Phoenix"),
    OptionChoice(name="Anchorage (AKST/AKDT)", value="America/Anchorage"),
    OptionChoice(name="Honolulu (HST, No DST)", value="Pacific/Honolulu"),
    OptionChoice(name="London (GMT/BST)", value="Europe/London"),
    OptionChoice(name="Paris (CET/CEST)", value="Europe/Paris"),
    OptionChoice(name="Istanbul (TRT)", value="Europe/Istanbul"),
    OptionChoice(name="Moscow (MSK)", value="Europe/Moscow"),
    OptionChoice(name="Dubai (GST)", value="Asia/Dubai"),
    OptionChoice(name="India (IST)", value="Asia/Kolkata"),
    OptionChoice(name="China/Singapore (CST)", value="Asia/Shanghai"),
    OptionChoice(name="Japan/Korea (JST/KST)", value="Asia/Tokyo"),
    OptionChoice(name="Bangkok (ICT)", value="Asia/Bangkok"),
    OptionChoice(name="Hong Kong (HKT)", value="Asia/Hong_Kong"),
    OptionChoice(name="Sydney (AEST/AEDT)", value="Australia/Sydney"),
    OptionChoice(name="Perth (AWST)", value="Australia/Perth"),
    OptionChoice(name="Cairo (EET/EEST)", value="Africa/Cairo"),
    OptionChoice(name="Lagos (WAT)", value="Africa/Lagos"),
    OptionChoice(name="Bogotá (COT)", value="America/Bogota"),
    OptionChoice(name="Mexico City (CST/CDT)", value="America/Mexico_City"),
    OptionChoice(name="São Paulo (BRT/BRST)", value="America/Sao_Paulo"),
]


class RemindersAdmin(Cog):
    reminder_cmd = SlashCommandGroup("reminder", "Manage reminders.")

    def __init__(self, bot: Bot):
        self.bot = bot

    async def fetch_reminders(self, *args: List[BinaryExpression]) -> List[Row]:
        async with Session.begin() as session:
            result = await session.execute(select(reminder).where(*args))
            reminders = result.all()

        return reminders

    def make_reminder_pages(self, reminder_rows: List[Row]) -> List[Embed]:
        pages = []

        for reminder_data in sorted(reminder_rows, key=lambda r: r.remind_at):
            embed = Embed()
            embed.description = f"### Reminder:\n{reminder_data.reminder_text}"

            value = "status: **{}**\nwhen: <t:{}:R>".format(
                reminder_data.status.value,
                int(reminder_data.remind_at.timestamp()),
            )
            embed.add_field(name="Reminder info:", value=value, inline=False)

            channel = self.bot.get_channel(reminder_data.channel_id)
            if channel is not None:
                original_message = channel.get_partial_message(
                    reminder_data.original_message_id
                )
                jump_url = original_message.jump_url
            else:
                jump_url = None

            if reminder_data.recurrence_interval is not None:
                recurrence_duration = duration(
                    seconds=reminder_data.recurrence_interval
                ).in_words()
            else:
                recurrence_duration = None

            value = (
                f"Reminder ID: {reminder_data.id}\n"
                f"owner: <@{reminder_data.owner}>\n"
                f"channel: <#{reminder_data.channel_id}>\n"
                f"original message: {jump_url}\n"
                f"is_recurring: {reminder_data.is_recurring}\n"
                f"recurrence_interval: {recurrence_duration}\n"
                f"created_at: <t:{int(reminder_data.created_at.timestamp())}:f>"
            )
            embed.add_field(name="Metadata:", value=value, inline=False)

            pages.append(embed)

        return pages

    @slash_command(description="Set default timezone for reminders.")
    @option("timezone", choices=TIMEZONE_CHOICES)
    async def set_timezone(self, ctx: ApplicationContext, timezone: str) -> None:
        logger.info("%s invoked /set_timezone with tz='%s'", ctx.author.name, timezone)

        async with Session.begin() as session:
            result = await session.execute(
                update(pzsd_user)
                .values(timezone=timezone)
                .where(pzsd_user.c.discord_snowflake == str(ctx.author.id))
            )

        if result.rowcount == 0:
            logger.info("Failed to set timezone, %s not in user table", ctx.author.name)
            await ctx.respond(
                "I can't set your timezone because you aren't registered. Ask an admin to register you first.",
                ephemeral=True,
            )
        else:
            await ctx.respond(f"Set timezone to '{timezone}'", ephemeral=True)

    @slash_command(description="Show reminders from every user.")
    @option(
        "user", description="Only show reminders from a specific user.", required=False
    )
    @default_permissions(administrator=True)
    async def list_all_reminders(self, ctx: ApplicationContext, user: Member) -> None:
        logger.info("%s invoked /list_all_reminders", ctx.author.name)

        if user is None:
            reminders = await self.fetch_reminders()
        else:
            reminders = await self.fetch_reminders(reminder.c.owner == user.id)

        pages = self.make_reminder_pages(reminders)

        if pages:
            paginator = Paginator(
                pages=pages,
                use_default_buttons=False,
                custom_buttons=get_page_buttons(),
            )

            await paginator.respond(ctx.interaction, ephemeral=True)
        else:
            await ctx.respond("No reminders found", ephemeral=True)

    @reminder_cmd.command(description="List your reminders.")
    async def list(self, ctx: ApplicationContext) -> None:
        logger.info("%s invoked /reminder list", ctx.author.name)

        reminders = await self.fetch_reminders(reminder.c.owner == ctx.author.id)
        pages = self.make_reminder_pages(reminders)

        if pages:
            paginator = Paginator(
                pages=pages,
                use_default_buttons=False,
                custom_buttons=get_page_buttons(),
            )

            await paginator.respond(ctx.interaction, ephemeral=True)
        else:
            await ctx.respond("You don't have any reminders", ephemeral=True)

    @reminder_cmd.command(description="Delete a reminder")
    @option("reminder_id", description="ID of the reminder to delete.")
    async def delete(self, ctx: ApplicationContext, reminder_id: int) -> None:
        logger.info(
            "%s invoked /reminder delete with id=%s", ctx.author.name, reminder_id
        )

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                delete(reminder)
                .where(reminder.c.id == reminder_id)
                .where(is_admin | (reminder.c.owner == ctx.author.id))
            )

        if result.rowcount > 0:
            logger.info("Deleted reminder with id=%s", reminder_id)

            await ctx.respond(f"Deleted reminder with id={reminder_id}", ephemeral=True)
        else:
            logger.info(
                "Reminder didn't exist or user didn't have permission to delete it"
            )

            await ctx.respond(
                f"Failed to delete reminder with id={reminder_id} (Doesn't exist or you don't have permission)",
                ephemeral=True,
            )


def setup(bot: Bot) -> None:
    bot.add_cog(RemindersAdmin(bot))
