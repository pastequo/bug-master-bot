from loguru import logger
from starlette.responses import Response

from .. import consts
from .command import Command


class ChannelConfigurationCommand(Command):
    @classmethod
    def get_description(cls) -> str:
        return "Get the last updated configurations file in the channel."

    async def handle(self) -> Response:
        logger.info(f"Handling {self._command}")

        channel_config = self._bot.get_configuration(self._channel_id)
        if not channel_config:
            logger.info(f"Attempting to load configurations for channel `{self._channel_id}:{self._channel_name}`")
            await self._bot.try_load_configurations_from_history(self._channel_id)
            channel_config = self._bot.get_configuration(self._channel_id)

        if channel_config is None:
            return self.get_response(
                f"Can't find configurations for channel `{self._channel_name}`. You can upload"
                f" configuration file (`{consts.CONFIGURATION_FILE_NAME}`) to the channel"
            )

        return self.get_response(f"Current channel configuration - <{channel_config.permalink} | link>")
