import logging
import re
from typing import Any, Dict, List, Tuple

from discord import Bot, InputTextStyle, Interaction
from discord.ui import InputText, Modal
from sqlalchemy import delete, func, insert, update

from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response

logger = logging.getLogger(__name__)


class _TriggerModalMixin:
    @staticmethod
    def is_valid_regex(pattern: str) -> bool:
        try:
            re.compile(pattern)
        except re.error:
            return False
        else:
            return True

    async def get_input(
        self, interaction: Interaction
    ) -> Tuple[List[str], List[str]] | None:
        if self.is_regex:
            pattern = self.children[0].value
            if self.is_valid_regex(pattern):
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

        responses = self.children[1].value.splitlines()

        return patterns, responses


class AddTriggerModal(Modal, _TriggerModalMixin):
    def __init__(
        self,
        *args: Tuple[Any, ...],
        is_regex: bool,
        response_type: str,
        bot: Bot,
        **kwargs: Dict[str, Any],
    ) -> None:
        super().__init__(*args, **kwargs)

        self.bot = bot

        self.is_regex = is_regex
        pattern_label = "Trigger {}pattern".format("regex " if is_regex else "")

        self.response_type = response_type

        self.add_item(InputText(label=pattern_label, style=InputTextStyle.long))
        self.add_item(InputText(label="Response(s)", style=InputTextStyle.long))

    async def add_trigger_to_db(
        self, owner: int, patterns: List[str], responses: List[str]
    ) -> int:
        logger.info("Adding new trigger to db")

        async with Session.begin() as session:
            result = await session.execute(
                insert(trigger_group)
                .values(owner=owner, response_type=self.response_type)
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

        return group_id

    async def callback(self, interaction: Interaction):
        logger.debug(
            "Performing AddTriggerModal callback for user with id=%s",
            interaction.user.id,
        )

        modal_input = await self.get_input(interaction)
        if modal_input is None:
            return

        patterns, responses = modal_input
        group_id = await self.add_trigger_to_db(
            interaction.user.id, patterns, responses
        )

        # send on_trigger_added event
        # to add trigger into memory
        self.bot.dispatch(
            "trigger_added",
            patterns=patterns,
            responses=responses,
            is_regex=self.is_regex,
            response_type=self.response_type,
            group_id=group_id,
        )

        await interaction.respond("Successfully added trigger", ephemeral=True)


class EditTriggerModal(Modal, _TriggerModalMixin):
    def __init__(
        self,
        *args: Tuple[Any, ...],
        patterns: List[str],
        responses: List[str],
        is_regex: bool,
        response_type: str,
        group_id: int,
        bot: Bot,
        **kwargs: Dict[str, Any],
    ) -> None:
        super().__init__(*args, **kwargs)

        self.bot = bot

        self.is_regex = is_regex
        pattern_label = "Trigger {}pattern".format("regex " if is_regex else "")

        self.response_type = response_type

        self.old_patterns = patterns
        self.group_id = group_id

        self.add_item(
            InputText(
                label=pattern_label,
                style=InputTextStyle.long,
                value=",".join(dict.fromkeys(patterns)),
            )
        )
        self.add_item(
            InputText(
                label="Response(s)",
                style=InputTextStyle.long,
                value="\n".join(dict.fromkeys(responses)),
            )
        )

    async def edit_trigger_in_db(
        self, new_patterns: List[str], new_responses: List[str]
    ) -> None:
        logger.info("Modifying trigger in db with id=%s", self.group_id)

        async with Session.begin() as session:
            await session.execute(
                delete(trigger_pattern).where(
                    trigger_pattern.c.group_id == self.group_id
                )
            )
            await session.execute(
                delete(trigger_response).where(
                    trigger_response.c.group_id == self.group_id
                )
            )

            await session.execute(
                insert(trigger_pattern),
                [
                    {
                        "pattern": pattern,
                        "group_id": self.group_id,
                        "is_regex": self.is_regex,
                    }
                    for pattern in new_patterns
                ],
            )
            await session.execute(
                insert(trigger_response),
                [
                    {
                        "response": response,
                        "group_id": self.group_id,
                    }
                    for response in new_responses
                ],
            )

            await session.execute(
                update(trigger_group)
                .where(trigger_group.c.id == self.group_id)
                .values(updated_at=func.now())
            )

    async def callback(self, interaction: Interaction):
        logger.debug(
            "Performing EditTriggerModal callback for user with id=%s",
            interaction.user.id,
        )

        modal_input = await self.get_input(interaction)
        if modal_input is None:
            return

        patterns, responses = modal_input

        await self.edit_trigger_in_db(patterns, responses)

        # send on_trigger_modified event
        # to edit trigger in memory
        self.bot.dispatch(
            "trigger_modified",
            old_patterns=self.old_patterns,
            new_patterns=patterns,
            new_responses=responses,
            is_regex=self.is_regex,
            response_type=self.response_type,
            group_id=self.group_id,
        )

        await interaction.respond("Successfully edited trigger", ephemeral=True)
