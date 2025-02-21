import logging
import re

from discord import Bot, InputTextStyle, Interaction
from discord.ui import InputText, Modal
from sqlalchemy import insert

from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response

logger = logging.getLogger(__name__)


def is_valid_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    else:
        return True


class AddTriggerModal(Modal):
    def __init__(self, *args, is_regex: bool, bot: Bot, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.bot = bot

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

        logger.info("Adding new trigger to db")

        async with Session.begin() as session:
            result = await session.execute(
                insert(trigger_group)
                .values(owner=interaction.user.id)
                .returning(trigger_group.c.id)
            )
            group_id: int = result.scalar_one()

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
        logger.info("Added trigger to db with group_id=%s", group_id)

        # send on_trigger_added event
        # to update triggers in memory
        self.bot.dispatch(
            "trigger_added",
            patterns=patterns,
            responses=responses,
            is_regex=self.is_regex,
            group_id=group_id,
        )

        await interaction.respond("Successfully added trigger")
