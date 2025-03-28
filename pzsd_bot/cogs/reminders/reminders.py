import asyncio
import logging
import re

import pendulum
from discord import Bot, Colour, Embed, Message
from discord.ext.commands import Cog
from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Row
from sqlalchemy.sql.functions import count

from pzsd_bot.db import Session
from pzsd_bot.ext.scheduler import Scheduler
from pzsd_bot.model import ReminderStatus, pzsd_user, reminder
from pzsd_bot.settings import Emoji, ReminderSettings

logger = logging.getLogger(__name__)

REMINDER_PATTERN = re.compile(
    r"remind me (?P<preposition>in|at|on) "
    r"(?P<time>.+?)((?: every )(?P<interval>.+))? "
    r"to (?P<reminder>.+)",
    re.IGNORECASE | re.DOTALL,
)
DURATION_PATTERN = re.compile(
    re.compile(
        r"((?P<years>\d+?) ?(years|year|Y|y) ?)?"
        r"((?P<months>\d+?) ?(months|month|m) ?)?"
        r"((?P<weeks>\d+?) ?(weeks|week|W|w) ?)?"
        r"((?P<days>\d+?) ?(days|day|D|d) ?)?"
        r"((?P<hours>\d+?) ?(hours|hour|hrs?|H|h) ?)?"
        r"((?P<minutes>\d+?) ?(minutes|minute|min|M) ?)?"
        r"((?P<seconds>\d+?) ?(seconds|second|secs?|S|s))?"
    )
)

MINIMUM_INTERVAL_FREQUENCY = pendulum.duration(days=1)
MAXIMUM_INTERVAL_FREQUENCY = pendulum.duration(seconds=2147483647)  # ~68 years


class Reminders(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = Scheduler(__class__.__name__)

        asyncio.create_task(self.load_reminders())

    @staticmethod
    def parse_relative_time(time: str) -> pendulum.Duration | None:
        if m := DURATION_PATTERN.fullmatch(time):
            duration = {
                unit: int(amount) for unit, amount in m.groupdict(default=0).items()
            }
            return pendulum.duration(**duration)

    @staticmethod
    def parse_absolute_time(time: str, timezone: str) -> pendulum.DateTime | None:
        try:
            return pendulum.parse(time, strict=False, tz=timezone)
        except pendulum.exceptions.ParserError:
            return None

    async def load_reminders(self) -> None:
        logger.info("Loading pending reminders and rescheduling them")

        async with Session.begin() as session:
            result = await session.execute(
                select(reminder).where(reminder.c.status == ReminderStatus.pending)
            )
            pending_reminders = result.all()

        for pending_reminder in pending_reminders:
            self.scheduler.schedule(
                run_at=pending_reminder.remind_at,
                task_id=f"reminder_{pending_reminder.id}",
                coroutine=self.send_reminder(pending_reminder),
            )
        logger.info("Scheduled %s reminders", len(pending_reminders))

    def cog_unload(self) -> None:
        self.scheduler.cancel_all()

    async def reschedule_reminder(self, reminder_data: Row) -> None:
        logger.info("Rescheduling recurring reminder (id=%s)", reminder_data.id)

        self.scheduler.schedule(
            run_at=reminder_data.remind_at,
            task_id=f"reminder_{reminder_data.id}",
            coroutine=self.send_reminder(reminder_data),
        )

    async def send_reminder(self, reminder_data: Row) -> None:
        logger.info("Attempting to send reminder (id=%s)", reminder_data.id)

        channel = self.bot.get_channel(reminder_data.channel_id)
        if channel is None:
            # channel may not be cached yet
            logger.debug("Couldn't find channel in cache, attempting to fetch")
            try:
                channel = await self.bot.fetch_channel(reminder_data.channel_id)
            except Exception as e:
                logger.warning(
                    "Failed to send reminder (id=%s), can't find channel (id=%s) with error: %s",
                    reminder_data.id,
                    reminder_data.channel_id,
                    e,
                )
                async with Session.begin() as session:
                    await session.execute(
                        update(reminder)
                        .values(status=ReminderStatus.failed)
                        .where(reminder.c.id == reminder_data.id)
                    )

                return

        original_message = channel.get_partial_message(
            reminder_data.original_message_id
        )
        embed = Embed(
            description=reminder_data.reminder_text,
            colour=Colour.blurple(),
        )
        await original_message.reply("Here's your reminder:", embed=embed)

        logger.info("Reminder sent (id=%s)", reminder_data.id)

        if reminder_data.is_recurring:
            new_remind_at = reminder_data.remind_at + pendulum.duration(
                seconds=reminder_data.recurrence_interval
            )
            async with Session.begin() as session:
                result = await session.execute(
                    update(reminder)
                    .values(remind_at=new_remind_at)
                    .where(reminder.c.id == reminder_data.id)
                    .returning(reminder)
                )
                reminder_data = result.one()

            asyncio.create_task(self.reschedule_reminder(reminder_data))
        else:
            logger.debug("Deleting reminder with id=%s", reminder_data.id)
            async with Session.begin() as session:
                await session.execute(
                    delete(reminder).where(reminder.c.id == reminder_data.id)
                )

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author == self.bot.user:
            return

        if (m := REMINDER_PATTERN.search(message.content)) is None:
            return

        if m["preposition"].lower() == "in":
            duration = self.parse_relative_time(m["time"])
            if duration:
                remind_at = pendulum.now() + duration
            else:
                remind_at = None
        elif m["preposition"].lower() in ("at", "on"):
            async with Session.begin() as session:
                result = await session.execute(
                    select(pzsd_user.c.timezone).where(
                        pzsd_user.c.discord_snowflake == str(message.author.id)
                    )
                )
                user_tz = result.scalar_one_or_none()

            try:
                remind_at = self.parse_absolute_time(m["time"], user_tz or "UTC")
            except pendulum.tz.exceptions.InvalidTimezone:
                logger.warning("%s has invalid timezone set", message.author.name)
                remind_at = None
            except Exception:
                logger.exception("Failed to parse time: '%s'", m["time"])
                remind_at = None

        if remind_at is None:
            logger.info(
                "%s gave invalid time format: '%s'", message.author.name, m["time"]
            )
            await message.add_reaction(Emoji.cross_mark)
            return

        is_recurring = m["interval"] is not None
        if is_recurring:
            interval = self.parse_relative_time(m["interval"])
            if interval is None:
                logger.info(
                    "%s gave invalid interval format: '%s'",
                    message.author.name,
                    m["interval"],
                )
                await message.add_reaction(Emoji.cross_mark)
                return
            elif interval < MINIMUM_INTERVAL_FREQUENCY:
                logger.info(
                    "%s gave an interval that's too short: '%s'",
                    message.author.name,
                    m["interval"],
                )
                await message.add_reaction(Emoji.nopers)
                return
            elif interval > MAXIMUM_INTERVAL_FREQUENCY:
                logger.info(
                    "%s gave an interval that's too long: '%s'",
                    message.author.name,
                    m["interval"],
                )
                await message.add_reaction(Emoji.nopers)
                return
        else:
            interval = None

        if interval:
            recurrence_interval = interval.in_seconds()
        else:
            recurrence_interval = None

        async with Session.begin() as session:
            result = await session.execute(
                select(count())
                .select_from(reminder)
                .where(reminder.c.owner == message.author.id)
                .where(reminder.c.status == ReminderStatus.pending)
            )
            reminder_count = result.scalar_one()

            if reminder_count < ReminderSettings.max_reminders:
                result = await session.execute(
                    insert(reminder)
                    .values(
                        owner=message.author.id,
                        channel_id=message.channel.id,
                        original_message_id=message.id,
                        reminder_text=m["reminder"],
                        remind_at=remind_at,
                        is_recurring=is_recurring,
                        recurrence_interval=recurrence_interval,
                    )
                    .returning(reminder)
                )
                new_reminder = result.one()
            else:
                logger.info(
                    "%s tried creating a reminder but it would exceed the max allowed (%s)",
                    message.author.name,
                    ReminderSettings.max_reminders,
                )
                await message.add_reaction(Emoji.nopers)
                return

        self.scheduler.schedule(
            run_at=new_reminder.remind_at,
            task_id=f"reminder_{new_reminder.id}",
            coroutine=self.send_reminder(new_reminder),
        )
        await message.add_reaction(Emoji.check_mark)
        abbreviated_reminder_invocation = (
            m[0][: m[0].find("to") + 2] + "\N{HORIZONTAL ELLIPSIS}"
        )
        logger.info(
            "%s created a reminder: '%s'",
            message.author.name,
            abbreviated_reminder_invocation,
        )


def setup(bot: Bot) -> None:
    bot.add_cog(Reminders(bot))
