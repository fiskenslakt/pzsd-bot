import asyncio
import logging
import random
import re
from collections import defaultdict
from typing import DefaultDict, List, Tuple

from discord import Bot, Message
from discord.ext.commands import Cog
from sqlalchemy import select

from pzsd_bot.db import Session
from pzsd_bot.model import (
    TriggerResponseType,
    trigger_group,
    trigger_pattern,
    trigger_response,
)

logger = logging.getLogger(__name__)

CachedTrigger = DefaultDict[Tuple[int, str, str], List[str]]


class Triggers(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.normal_triggers: CachedTrigger = defaultdict(list)
        self.regex_triggers: CachedTrigger = defaultdict(list)

        asyncio.create_task(self.load_triggers())

    async def load_triggers(self) -> None:
        logger.info("Loading triggers into memory")
        tp = trigger_pattern.columns
        tr = trigger_response.columns
        tg = trigger_group.columns
        async with Session.begin() as session:
            result = await session.execute(
                select(
                    tp.group_id, tp.pattern, tp.is_regex, tg.response_type, tr.response
                )
                .join(trigger_group, tp.group_id == tg.id)
                .join(trigger_response, tg.id == tr.group_id)
                .where(tg.is_active == True)
            )
            triggers = result.all()

        normal_trigger_groups = set()
        regex_trigger_groups = set()
        for trigger in triggers:
            key = trigger.group_id, trigger.pattern, trigger.response_type
            if trigger.is_regex:
                self.regex_triggers[key].append(trigger.response)
                regex_trigger_groups.add(trigger.group_id)
            else:
                self.normal_triggers[key].append(trigger.response)
                normal_trigger_groups.add(trigger.group_id)

        total_triggers = len(regex_trigger_groups) + len(normal_trigger_groups)
        logger.info(
            "Loaded %s triggers (%s regex, %s normal)",
            total_triggers,
            len(regex_trigger_groups),
            len(normal_trigger_groups),
        )

    @Cog.listener()
    async def on_trigger_added(
        self,
        patterns: List[str],
        responses: List[str],
        is_regex: bool,
        response_type: str,
        group_id: int,
    ) -> None:
        logger.info("Trigger was added, updating triggers in memory")

        for pattern in patterns:
            key = group_id, pattern, response_type
            if is_regex:
                self.regex_triggers[key] = responses
            else:
                self.normal_triggers[key] = responses

    @Cog.listener()
    async def on_trigger_removed(
        self, patterns: List[str], is_regex: bool, response_type: str, group_id: int
    ) -> None:
        logger.info("Trigger was removed, updating triggers in memory")

        for pattern in patterns:
            key = group_id, pattern, response_type
            if is_regex:
                self.regex_triggers.pop(key, None)
            else:
                self.normal_triggers.pop(key, None)

    @Cog.listener()
    async def on_trigger_modified(
        self,
        old_patterns: List[str],
        new_patterns: List[str],
        new_responses: List[str],
        is_regex: bool,
        response_type: str,
        group_id: int,
    ) -> None:
        logger.info("Trigger was modified, updating triggers in memory")

        for old_pattern in old_patterns:
            old_key = group_id, old_pattern, response_type
            if is_regex:
                self.regex_triggers.pop(old_key, None)
            else:
                self.normal_triggers.pop(old_key, None)

        for new_pattern in new_patterns:
            new_key = group_id, new_pattern, response_type
            if is_regex:
                self.regex_triggers[new_key] = new_responses
            else:
                self.normal_triggers[new_key] = new_responses

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author == self.bot.user:
            return

        for (
            group_id,
            pattern,
            response_type,
        ), responses in self.normal_triggers.items():
            if pattern in message.content.lower():
                logger.info(
                    "Pattern match on '%s' (id=%s) in %s's message",
                    pattern,
                    group_id,
                    message.author.name,
                )
                match response_type:
                    case TriggerResponseType.standard.value:
                        await message.channel.send(random.choice(responses))
                    case TriggerResponseType.reply.value:
                        await message.reply(random.choice(responses))
                    case TriggerResponseType.reaction.value:
                        await message.add_reaction(random.choice(responses))

        for (
            group_id,
            pattern,
            response_type,
        ), responses in self.regex_triggers.items():
            m = re.search(pattern, message.content, re.IGNORECASE)
            if m:
                logger.info(
                    "Pattern match on '%s' (id=%s, matched '%s') in %s's message",
                    pattern,
                    group_id,
                    m[0],
                    message.author.name,
                )
                response = m.expand(random.choice(responses))

                match response_type:
                    case TriggerResponseType.standard.value:
                        await message.channel.send(response)
                    case TriggerResponseType.reply.value:
                        await message.reply(response)
                    case TriggerResponseType.reaction.value:
                        await message.add_reaction(response)


def setup(bot: Bot) -> None:
    bot.add_cog(Triggers(bot))
