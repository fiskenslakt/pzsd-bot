import logging

from discord import ApplicationContext, Bot, default_permissions
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog
from sqlalchemy import select, update, func, true, false
from sqlalchemy.sql.functions import count

from pzsd_bot.ui.triggers.modals import AddTriggerModal
from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response
from pzsd_bot.settings import Roles

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

    @trigger_cmd.command(description="List triggers from all users.")
    @default_permissions(administrator=True)
    async def list_all(self, ctx: ApplicationContext) -> None:
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
        logger.info("%s invoked /trigger disable with id=%s", ctx.author.name, trigger_id)

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                update(trigger_group)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
                .values(is_active=False)
            )

            trigger_result = await session.execute(
                select(trigger_pattern.c.pattern, trigger_pattern.c.is_regex)
                .where(trigger_pattern.c.group_id == trigger_id)
            )
            trigger = trigger_result.all()

        if result.rowcount > 0:
            logger.info("Disabled trigger with id=%s", trigger_id)

            patterns = []
            for t in trigger:
                patterns.append(t.pattern)

            # send on_trigger_removed event
            # to remove trigger from memory
            self.bot.dispatch(
                "trigger_removed",
                patterns=patterns,
                is_regex=t.is_regex,
                group_id=trigger_id,
            )

            await ctx.respond(f"Disabled trigger with id={trigger_id}", ephemeral=True)
        else:
            logger.info("Trigger didn't exist or user didn't have permission to disable it")
            await ctx.respond(f"Failed to disable trigger with id={trigger_id} (Doesn't exist or you don't have permission)", ephemeral=True)

    @trigger_cmd.command(description="Enable trigger.")
    @option("trigger_id", description="ID of the trigger to enable.")
    async def enable(self, ctx: ApplicationContext, trigger_id: int) -> None:
        logger.info("%s invoked /trigger enable with id=%s", ctx.author.name, trigger_id)

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                update(trigger_group)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
                .values(is_active=True, updated_at=func.now())
            )

            trigger_result = await session.execute(
                select(trigger_pattern.c.pattern, trigger_response.c.response, trigger_pattern.c.is_regex)
                .join(trigger_response, trigger_pattern.c.group_id == trigger_response.c.group_id)
                .where(trigger_pattern.c.group_id == trigger_id)
            )
            trigger = trigger_result.all()

        if result.rowcount > 0:
            logger.info("Enabled trigger with id=%s", trigger_id)

            patterns = []
            responses = []
            for t in trigger:
                patterns.append(t.pattern)
                responses.append(t.response)

            # send on_trigger_added event
            # to add trigger into memory
            self.bot.dispatch(
                "trigger_added",
                patterns=patterns,
                responses=responses,
                is_regex=t.is_regex,
                group_id=trigger_id,
            )

            await ctx.respond(f"Enabled trigger with id={trigger_id}", ephemeral=True)
        else:
            logger.info("Trigger didn't exist or user didn't have permission to enable it")
            await ctx.respond(f"Failed to enable trigger with id={trigger_id} (Doesn't exist or you don't have permission)", ephemeral=True)


def setup(bot: Bot) -> None:
    bot.add_cog(TriggerAdmin(bot))
