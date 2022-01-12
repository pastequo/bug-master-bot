from abc import ABC, abstractmethod
from typing import Dict

from bug_master.bug_master_bot import BugMasterBot

from ..consts import logger


class Command(ABC):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        self._bot = bot
        self._channel_id = kwargs.get("channel_id")
        self._channel_name = kwargs.get("channel_name")
        self._command = kwargs.get("text")

    @abstractmethod
    async def handle(self) -> Dict[str, str]:
        pass

    @classmethod
    def get_response(cls, text: str):
        return {"response_type": "in_channel", "text": text}


class GetChannelCommand(Command):
    async def handle(self) -> Dict[str, str]:
        logger.info(f"Handling {self._command}")

        channel_config = self._bot.get_configuration(self._channel_id)
        if not channel_config:
            logger.info(f"Attempting to load configurations for channel `{self._channel_id}:{self._channel_name}`")
            await self._bot.try_load_configurations_from_history(self._channel_id)
            channel_config = self._bot.get_configuration(self._channel_id)

        if not channel_config:
            return self.get_response(
                f"Can't find configurations for channel `{self._channel_name}`. You can upload"
                f' configuration file ("bug_master_configuration.yaml") to the channel'
            )

        return self.get_response(f"Current channel configuration - <{channel_config.permalink} | link>")
