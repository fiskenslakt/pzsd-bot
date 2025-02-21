import logging

from discord import ApplicationContext, Bot
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from pzsd_bot.ui.triggers.modals import AddTriggerModal
from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group

logger = logging.getLogger(__name__)

NORMAL_TRIGGERS_LIMIT = 200
REGEX_TRIGGERS_LIMIT = 100


class TriggerAdmin(Cog):
    trigger_cmd = SlashCommandGroup("trigger", "Manage triggers.")

    def __init__(self, bot: Bot):
        self.bot = bot

    @trigger_cmd.command(description="Add a trigger.")
    @option(
        "is_regex",
        description="If pattern should be considered a regex.",
        default=False,
        choices=[True, False],
    )
    async def add(self, ctx: ApplicationContext, is_regex: bool) -> None:
        logger.info(
            "%s invoked /trigger add with is_regex=%s", ctx.author.name, is_regex
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(count())
                .select_from(trigger_group)
                .where(trigger_group.c.owner == ctx.author.id)
            )
            trigger_count = result.scalar_one()

        if is_regex and trigger_count >= REGEX_TRIGGERS_LIMIT:
            logger.info(
                "%s can't add new trigger because it would exceed maximum allowed regex triggers",
                ctx.author.name,
            )
            await ctx.respond("Holy cow! You have too many regex triggers!")
            return

        if not is_regex and trigger_count >= NORMAL_TRIGGERS_LIMIT:
            logger.info(
                "%s can't add new trigger because it would exceed maximum allowed triggers",
                ctx.author.name,
            )
            await ctx.respond("Holy cow! You have too many triggers!")
            return

        modal = AddTriggerModal(title="New trigger", is_regex=is_regex, bot=self.bot)
        await ctx.send_modal(modal)

    @trigger_cmd.command(description="List triggers.")
    async def list(self, ctx: ApplicationContext) -> None:
        pass

    @trigger_cmd.command(description="Edit trigger.")
    @option("trigger_id", description="ID of the trigger to edit.")
    async def edit(self, ctx: ApplicationContext, trigger_id: int) -> None:
        pass

    @trigger_cmd.command(description="Delete trigger.")
    @option("trigger_id", description="ID of the trigger to delete.")
    async def delete(self, ctx: ApplicationContext, trigger_id: int) -> None:
        pass

    @trigger_cmd.command(description="Disable trigger.")
    @option("trigger_id", description="ID of the trigger to disable.")
    async def disable(self, ctx: ApplicationContext, trigger_id: int) -> None:
        pass

    @trigger_cmd.command(description="Enable trigger.")
    @option("trigger_id", description="ID of the trigger to enable.")
    async def enable(self, ctx: ApplicationContext, trigger_id: int) -> None:
        pass


def setup(bot: Bot) -> None:
    bot.add_cog(TriggerAdmin(bot))
