import logging
from typing import List

from discord import ApplicationContext, Bot, Embed, Member, default_permissions
from discord.commands import SlashCommandGroup, option
from discord.ext.commands import Cog
from discord.ext.pages import Paginator
from sqlalchemy import delete, false, func, select, true, update
from sqlalchemy.engine import Row
from sqlalchemy.sql.elements import BinaryExpression
from sqlalchemy.sql.functions import count

from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response
from pzsd_bot.settings import Roles
from pzsd_bot.ui.buttons import get_page_buttons
from pzsd_bot.ui.triggers.modals import AddTriggerModal, EditTriggerModal

logger = logging.getLogger(__name__)

NORMAL_TRIGGERS_LIMIT = 200
REGEX_TRIGGERS_LIMIT = 100


class TriggerAdmin(Cog):
    trigger_cmd = SlashCommandGroup("trigger", "Manage triggers.")

    def __init__(self, bot: Bot):
        self.bot = bot

    async def fetch_triggers(self, *args: List[BinaryExpression]) -> List[Row]:
        TP = trigger_pattern.columns
        TR = trigger_response.columns
        TG = trigger_group.columns
        async with Session.begin() as session:
            result = await session.execute(
                select(
                    TG.id,
                    TG.is_active,
                    TP.is_regex,
                    TG.owner,
                    TG.created_at,
                    TG.updated_at,
                    TP.pattern,
                    TR.response,
                )
                .join(trigger_group, TP.group_id == TG.id)
                .join(trigger_response, TG.id == TR.group_id)
                .where(*args)
            )
            trigger_rows = result.all()

        return trigger_rows

    def make_trigger_pages(self, trigger_rows: List[Row]) -> List[Embed]:
        triggers = {}
        for trigger in trigger_rows:
            if trigger.id not in triggers:
                triggers[trigger.id] = {
                    "trigger_id": trigger.id,
                    "is_regex": trigger.is_regex,
                    "is_active": trigger.is_active,
                    "owner": f"<@{trigger.owner}>",
                    "created_at": f"<t:{int(trigger.created_at.timestamp())}:f>",
                    "updated_at": f"<t:{int(trigger.updated_at.timestamp())}:f>",
                    "pattern": [trigger.pattern],
                    "response": [trigger.response],
                }
            else:
                triggers[trigger.id]["pattern"].append(trigger.pattern)
                triggers[trigger.id]["response"].append(trigger.response)

        pages = []
        for trigger in sorted(triggers.values(), key=lambda t: t["pattern"][0]):
            embed = Embed(title="All Triggers")
            patterns = ",".join(dict.fromkeys(trigger["pattern"]))

            responses = list(dict.fromkeys(trigger["response"]))
            embed.description = f"# {patterns}\n### Responses:\n"
            for response in responses:
                embed.description += f"* {response}\n"

            value = "Trigger ID: {}\nowner: {}\nis_active: {}\nis_regex: {}\ncreated_at: {}\nupdated_at: {}".format(
                trigger["trigger_id"],
                trigger["owner"],
                trigger["is_active"],
                trigger["is_regex"],
                trigger["created_at"],
                trigger["updated_at"],
            )
            embed.add_field(name="Metadata:", value=value)
            pages.append(embed)

        return pages

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
        logger.info("%s invoked /trigger list", ctx.author.name)

        trigger_rows = await self.fetch_triggers(trigger_group.c.owner == ctx.author.id)

        pages = self.make_trigger_pages(trigger_rows)
        if pages:
            paginator = Paginator(
                pages=pages,
                use_default_buttons=False,
                custom_buttons=get_page_buttons(),
            )

            await paginator.respond(ctx.interaction, ephemeral=True)
        else:
            await ctx.respond("You don't have any triggers", ephemeral=True)

    @trigger_cmd.command(description="List triggers from all users.")
    @option(
        "user", description="Only show triggers from a specific user.", required=False
    )
    @default_permissions(administrator=True)
    async def list_all(self, ctx: ApplicationContext, user: Member) -> None:
        logger.info(
            "%s invoked /trigger list_all with user=%s",
            ctx.author.name,
            getattr(user, "name", None),
        )

        if user is not None:
            trigger_rows = await self.fetch_triggers(trigger_group.c.owner == user.id)
        else:
            trigger_rows = await self.fetch_triggers()

        pages = self.make_trigger_pages(trigger_rows)
        if pages:
            paginator = Paginator(
                pages=pages,
                use_default_buttons=False,
                custom_buttons=get_page_buttons(),
            )

            await paginator.respond(ctx.interaction, ephemeral=True)
        else:
            await ctx.respond("No triggers exist", ephemeral=True)

    @trigger_cmd.command(description="Edit trigger.")
    @option("trigger_id", description="ID of the trigger to edit.")
    async def edit(self, ctx: ApplicationContext, trigger_id: int) -> None:
        logger.info("%s invoked /trigger edit with id=%s", ctx.author.name, trigger_id)

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                select(
                    trigger_pattern.c.pattern,
                    trigger_response.c.response,
                    trigger_pattern.c.is_regex,
                )
                .join(
                    trigger_response,
                    trigger_pattern.c.group_id == trigger_response.c.group_id,
                )
                .join(trigger_group, trigger_group.c.id == trigger_response.c.group_id)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
            )
            trigger = result.all()

        if not trigger:
            logger.info(
                "Trigger with id=%s doesn't exist or user doesn't have permission to edit it",
                trigger_id,
            )
            await ctx.respond(
                "Failed to edit trigger (doesn't exist or you don't have permission to edit it)",
                ephemeral=True,
            )
            return

        patterns = [t.pattern for t in trigger]
        responses = [t.response for t in trigger]
        is_regex = trigger[0].is_regex

        modal = EditTriggerModal(
            title="Edit trigger",
            patterns=patterns,
            responses=responses,
            is_regex=is_regex,
            group_id=trigger_id,
            bot=self.bot,
        )
        await ctx.send_modal(modal)

    @trigger_cmd.command(description="Delete trigger.")
    @option("trigger_id", description="ID of the trigger to delete.")
    async def delete(self, ctx: ApplicationContext, trigger_id: int) -> None:
        logger.info(
            "%s invoked /trigger delete with id=%s", ctx.author.name, trigger_id
        )

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            trigger_result = await session.execute(
                select(trigger_pattern.c.pattern, trigger_pattern.c.is_regex).where(
                    trigger_pattern.c.group_id == trigger_id
                )
            )
            trigger = trigger_result.all()

            result = await session.execute(
                delete(trigger_group)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
            )

        if result.rowcount > 0:
            logger.info("Deleted trigger with id=%s", trigger_id)

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

            await ctx.respond(f"Deleted trigger with id={trigger_id}", ephemeral=True)
        else:
            logger.info(
                "Trigger didn't exist or user didn't have permission to delete it"
            )
            await ctx.respond(
                f"Failed to delete trigger with id={trigger_id} (Doesn't exist or you don't have permission)",
                ephemeral=True,
            )

    @trigger_cmd.command(description="Disable trigger.")
    @option("trigger_id", description="ID of the trigger to disable.")
    async def disable(self, ctx: ApplicationContext, trigger_id: int) -> None:
        logger.info(
            "%s invoked /trigger disable with id=%s", ctx.author.name, trigger_id
        )

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                update(trigger_group)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
                .values(is_active=False, updated_at=func.now())
            )

            trigger_result = await session.execute(
                select(trigger_pattern.c.pattern, trigger_pattern.c.is_regex).where(
                    trigger_pattern.c.group_id == trigger_id
                )
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
            logger.info(
                "Trigger didn't exist or user didn't have permission to disable it"
            )
            await ctx.respond(
                f"Failed to disable trigger with id={trigger_id} (Doesn't exist or you don't have permission)",
                ephemeral=True,
            )

    @trigger_cmd.command(description="Enable trigger.")
    @option("trigger_id", description="ID of the trigger to enable.")
    async def enable(self, ctx: ApplicationContext, trigger_id: int) -> None:
        logger.info(
            "%s invoked /trigger enable with id=%s", ctx.author.name, trigger_id
        )

        is_admin = true() if ctx.author.get_role(Roles.admin) is not None else false()

        async with Session.begin() as session:
            result = await session.execute(
                update(trigger_group)
                .where(trigger_group.c.id == trigger_id)
                .where(is_admin | (trigger_group.c.owner == ctx.author.id))
                .values(is_active=True, updated_at=func.now())
            )

            trigger_result = await session.execute(
                select(
                    trigger_pattern.c.pattern,
                    trigger_response.c.response,
                    trigger_pattern.c.is_regex,
                )
                .join(
                    trigger_response,
                    trigger_pattern.c.group_id == trigger_response.c.group_id,
                )
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
            logger.info(
                "Trigger didn't exist or user didn't have permission to enable it"
            )
            await ctx.respond(
                f"Failed to enable trigger with id={trigger_id} (Doesn't exist or you don't have permission)",
                ephemeral=True,
            )


def setup(bot: Bot) -> None:
    bot.add_cog(TriggerAdmin(bot))
