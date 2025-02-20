import asyncio
import logging
import random
import re
from collections import defaultdict
from typing import DefaultDict, List

from discord import Bot, Message
from discord.ext.commands import Cog
from sqlalchemy import select

from pzsd_bot.db import Session
from pzsd_bot.model import trigger_group, trigger_pattern, trigger_response

logger = logging.getLogger(__name__)


class Triggers(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

        self.normal_triggers: DefaultDict[str, List[str]] = defaultdict(list)
        self.regex_triggers: DefaultDict[str, List[str]] = defaultdict(list)

        asyncio.create_task(self.load_triggers())

    async def load_triggers(self):
        logger.info("Loading triggers into memory")
        TP = trigger_pattern.columns
        TR = trigger_response.columns
        TG = trigger_group.columns
        async with Session.begin() as session:
            result = await session.execute(
                select(TP.pattern, TP.is_regex, TR.response)
                .join(trigger_group, TP.group_id == TG.id)
                .join(trigger_response, TG.id == TR.group_id)
                .where(TG.is_active == True)
            )
            triggers = result.all()

        for trigger in triggers:
            if trigger.is_regex:
                self.regex_triggers[trigger.pattern].append(trigger.response)
            else:
                self.normal_triggers[trigger.pattern].append(trigger.response)

        total_triggers = len(self.regex_triggers) + len(self.normal_triggers)
        logger.info(
            "Loaded %s triggers (%s regex, %s normal)",
            total_triggers,
            len(self.regex_triggers),
            len(self.normal_triggers),
        )

    @Cog.listener()
    async def on_trigger_added(
        self, patterns: List[str], responses: List[str], is_regex: bool
    ) -> None:
        logger.info("Updating triggers in memory")

        for pattern in patterns:
            if is_regex:
                self.regex_triggers[pattern] = responses
            else:
                self.normal_triggers[pattern] = responses

    @Cog.listener()
    async def on_trigger_removed(self) -> None:
        pass

    @Cog.listener()
    async def on_message(self, message: Message) -> None:
        if message.author == self.bot.user:
            return

        for pattern, responses in self.normal_triggers.items():
            if pattern in message.content.lower():
                logger.info(
                    "Pattern match on '%s' in %s's message",
                    pattern,
                    message.author.name,
                )
                await message.channel.send(random.choice(responses))

        for pattern, responses in self.regex_triggers.items():
            m = re.search(pattern, message.content, re.IGNORECASE)
            if m:
                logger.info(
                    "Pattern match on '%s' (matched '%s') in %s's message",
                    pattern,
                    m[0],
                    message.author.name,
                )
                response = random.choice(responses)
                await message.channel.send(m.expand(response))


def setup(bot: Bot) -> None:
    bot.add_cog(Triggers(bot))
