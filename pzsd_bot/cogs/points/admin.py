import logging
from enum import Enum, auto
from itertools import batched

from discord import ApplicationContext, Bot, Embed, default_permissions
from discord.commands import option
from discord.ext.commands import Cog, slash_command
from discord.ext.pages import Paginator
from sqlalchemy import insert, select, update

from pzsd_bot.db import Session
from pzsd_bot.model import pzsd_user
from pzsd_bot.settings import PointsSettings

logger = logging.getLogger(__name__)


class NameState(Enum):
    VALID_NAME = auto()
    INVALID_NAME = auto()
    DISALLOWED_NAME = auto()


class PointUserAdmin(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    def validate_name(self, name: str) -> NameState:
        if name in PointsSettings.disallowed_names:
            return NameState.DISALLOWED_NAME
        elif not PointsSettings.valid_name_pattern.fullmatch(name):
            return NameState.INVALID_NAME
        return NameState.VALID_NAME

    @slash_command(description="Add new name that can be bestowed points.")
    @option("name", description="The exact name to use when bestowing points.")
    @option("snowflake", description="Their discord ID if applicable.", required=False)
    @option(
        "point_giver",
        description="Determines if this user can bestow points.",
        default=False,
        choices=[True, False],
    )
    @default_permissions(administrator=True)
    async def register(
        self, ctx: ApplicationContext, name: str, snowflake: str, point_giver: bool
    ) -> None:
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /register with name='%s' snowflake=%s point_giver=%s",
            ctx.author.name,
            name,
            snowflake,
            point_giver,
        )

        name_state = self.validate_name(name)

        if name_state is NameState.DISALLOWED_NAME:
            logger.info("The name '%s' is not allowed, doing nothing", name)
            await ctx.respond(f"You cannot register the name '{name}'!")
            return
        elif name_state is NameState.INVALID_NAME:
            logger.info("'%s' is an invalid name, doing nothing", name)
            await ctx.respond(f"{name} is an invalid name, try something else.")
            return

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == name)
            )

        user_to_add = result.one_or_none()
        if user_to_add is not None:
            if user_to_add.is_active:
                logger.info("User '%s' already exists, doing nothing", name)
                await ctx.respond(f"'{name}' already exists!")
                return
            else:
                logger.info("User '%s' exists but is inactive", name)
                async with Session.begin() as session:
                    await session.execute(
                        update(pzsd_user)
                        .where(pzsd_user.c.name == name)
                        .values(
                            is_active=True,
                            discord_snowflake=snowflake,
                            point_giver=point_giver,
                        )
                    )
                logger.info("Reactivated user '%s' in user table", name)
                await ctx.respond(f"Reactivated user with name {name}")
        else:
            async with Session.begin() as session:
                await session.execute(
                    insert(pzsd_user).values(
                        name=name,
                        discord_snowflake=snowflake,
                        point_giver=point_giver,
                    )
                )
            logger.info("Added user '%s' to user table", name)
            await ctx.respond(f"Added user with name {name}")

    @slash_command(
        description="Remove name from being able to be bestowed points.",
    )
    @option("name", description="The exact name in the user table")
    @default_permissions(administrator=True)
    async def unregister(self, ctx: ApplicationContext, name: str) -> None:
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /unregister with name=%s",
            ctx.author.name,
            name,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == name)
            )

        user_to_del = result.one_or_none()
        if user_to_del is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", name)
            await ctx.respond(f"User '{name}' already doesn't exist!")
            return
        elif not user_to_del.is_active:
            logger.info("User '%s' is currently inactive, doing nothing", name)
            await ctx.respond(f"User '{name}' is already inactive!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.name == name)
                .values(is_active=False)
            )

        logger.info("Deactivated user '%s' in user table", name)
        await ctx.respond(f"Deactivated user with name {name}")

    @slash_command(description="Show user table.")
    @default_permissions(administrator=True)
    async def users(self, ctx: ApplicationContext) -> None:
        logger.info("%s invoked /users", ctx.author.name)

        async with Session.begin() as session:
            users = await session.execute(select(pzsd_user))

        pages = []

        for page in batched(sorted(users, key=lambda u: u.name), 5):
            embed = Embed(title="User List")
            for user in page:
                value = "Snowflake: {}\nActive: {}\nPoint Giver: {}\nCreated: <t:{}:f>"
                value = value.format(
                    user.discord_snowflake or "N/A",
                    user.is_active,
                    user.point_giver,
                    int(user.created_at.timestamp()),
                )
                embed.add_field(name=user.name, value=value, inline=False)
            pages.append(embed)

        paginator = Paginator(
            pages=pages,
            disable_on_timeout=False,
            author_check=True,
            use_default_buttons=False,
            custom_buttons=PointsSettings.page_buttons,
        )

        await paginator.respond(ctx.interaction)

    @slash_command(description="Rename user in user table.")
    @option("user", description="User in user table to rename.")
    @option("name", description="Name to give user.")
    @default_permissions(administrator=True)
    async def rename(self, ctx: ApplicationContext, user: str, name: str) -> None:
        user = user.lower().strip("\"' \n\t")
        name = name.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /rename with user='%s' name='%s'",
            ctx.author.name,
            user,
            name,
        )

        if user == name:
            logger.info(
                "Attempting to rename '%s' to the same name, doing nothing.", user
            )
            return

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_rename = result.one_or_none()
        if user_to_rename is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return

        name_state = self.validate_name(name)

        if name_state is NameState.DISALLOWED_NAME:
            logger.info("The name '%s' is not allowed, doing nothing", name)
            await ctx.respond(f"You cannot use the name '{name}'!")
            return
        elif name_state is NameState.INVALID_NAME:
            logger.info("'%s' is an invalid name, doing nothing", name)
            await ctx.respond(f"{name} is an invalid name, try something else.")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_rename.id)
                .values(name=name)
            )

        logger.info("Renamed user '%s' to '%s'", user, name)
        await ctx.respond(f"Renamed {user} to {name}")

    @slash_command(description="Endow user with point giving abilities.")
    @option("user", description="User in user table to endow.")
    @default_permissions(administrator=True)
    async def endow(self, ctx: ApplicationContext, user: str) -> None:
        user = user.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /endow with user='%s'",
            ctx.author.name,
            user,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_endow = result.one_or_none()
        if user_to_endow is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return
        elif user_to_endow.point_giver:
            logger.info("User '%s' is already a point giver, doing nothing", user)
            await ctx.respond(f"{user} can already give points!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_endow.id)
                .values(point_giver=True)
            )

        logger.info("Endowed user '%s' with point giving abilities", user)
        await ctx.respond(f"Endowed {user} with point giving abilities.")

    @slash_command(description="Remove user's ability to give points.")
    @option("user", description="User in user table to disendow.")
    @default_permissions(administrator=True)
    async def disendow(self, ctx: ApplicationContext, user: str) -> None:
        user = user.lower().strip("\"' \n\t")

        logger.info(
            "%s invoked /disendow with user='%s'",
            ctx.author.name,
            user,
        )

        async with Session.begin() as session:
            result = await session.execute(
                select(pzsd_user).where(pzsd_user.c.name == user)
            )

        user_to_disendow = result.one_or_none()
        if user_to_disendow is None:
            logger.info("User '%s' doesn't exist in user table, doing nothing", user)
            await ctx.respond(f"User '{user}' doesn't exist!")
            return
        elif not user_to_disendow.point_giver:
            logger.info("User '%s' isn't a point giver, doing nothing", user)
            await ctx.respond(f"{user} isn't a point giver already!")
            return

        async with Session.begin() as session:
            await session.execute(
                update(pzsd_user)
                .where(pzsd_user.c.id == user_to_disendow.id)
                .values(point_giver=False)
            )

        logger.info("Removed ability to give points from user '%s'", user)
        await ctx.respond(f"Disendowed {user}")


def setup(bot: Bot) -> None:
    bot.add_cog(PointUserAdmin(bot))
