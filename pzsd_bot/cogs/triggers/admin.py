import logging
import re

from discord import ApplicationContext, Bot, InputTextStyle, Interaction
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog
from discord.ui import InputText, Modal
from sqlalchemy import insert, select
from sqlalchemy.sql.functions import count

from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response

logger = logging.getLogger(__name__)

NORMAL_TRIGGERS_LIMIT = 200
REGEX_TRIGGERS_LIMIT = 100


def is_valid_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    else:
        return True


class AddTriggerModal(Modal):
    def __init__(self, *args, is_regex: bool, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.is_regex = is_regex
        pattern_label = "Trigger {}pattern".format("regex " if is_regex else "")

        self.add_item(InputText(label=pattern_label, style=InputTextStyle.long))
        self.add_item(InputText(label="Response(s)", style=InputTextStyle.long))

    async def callback(self, interaction: Interaction):
        logger.debug(
            "Performing AddTriggerModal callback for user with id=%s",
            interaction.user.id,
        )

        if self.is_regex:
            pattern = self.children[0].value
            if pattern and is_valid_regex(pattern):
                patterns = [pattern]
            else:
                logger.info(
                    "%s submitted trigger with invalid regex, doing nothing.",
                    interaction.user.name,
                )
                await interaction.respond("Invalid regex, failed to add trigger.")
                return
        else:
            patterns = self.children[0].value.lower().split(",")

        # TODO confirm if this is how i want to parse responses
        responses = self.children[1].value.splitlines()

        logger.info("Adding new trigger(s) to db")

        async with Session.begin() as session:
            result = await session.execute(
                insert(trigger_group)
                .values(owner=interaction.user.id)
                .returning(trigger_group.c.id)
            )
            group_id = result.scalar_one()

            await session.execute(
                insert(trigger_pattern),
                [
                    {
                        "pattern": pattern,
                        "group_id": group_id,
                        "is_regex": self.is_regex,
                    }
                    for pattern in patterns
                ],
            )
            await session.execute(
                insert(trigger_response),
                [
                    {
                        "response": response,
                        "group_id": group_id,
                    }
                    for response in responses
                ],
            )
        logger.info("Added triggers to db with group_id=%s", group_id)

        await interaction.respond("Successfully added trigger")


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

        modal = AddTriggerModal(title="New trigger", is_regex=is_regex)
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
