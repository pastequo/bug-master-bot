from typing import Dict

import yaml
from loguru import logger
from starlette.responses import Response

from .. import consts
from ..channel_config_handler import BaseChannelConfig
from .command import Command


class ChannelConfigurationCommand(Command):
    @classmethod
    def get_description(cls) -> str:
        return "Get the last updated configurations file in the channel."

    @classmethod
    def command(cls):
        return "config"

    async def get_configuration_link(self):
        channel_config = self._bot.get_configuration(self._channel_id)
        if not channel_config:
            logger.info(f"Attempting to load configurations for channel `{self._channel_id}:{self._channel_name}`")
            await self._bot.try_load_configurations_from_history(self._channel_id)
            channel_config = self._bot.get_configuration(self._channel_id)

        if channel_config is None:
            return self.get_response_with_command(
                f"Can't find configurations for channel `{self._channel_name}`. You can upload"
                f" configuration file (`{consts.CONFIGURATION_FILE_NAME}`) to the channel"
            )

        remote_config_msg = f". Remote configurations can be found <{channel_config.remote_repository} | here>."
        return self.get_response_with_command(
            f"Current channel configuration - <{channel_config.permalink} | link>"
            + (remote_config_msg if channel_config.remote_url else "")
        )

    def get_config_schema(self) -> Response:
        schema = BaseChannelConfig.get_config_schema()
        json_schema = {k: v for k, v in schema.json_schema(self._channel_id).items() if not k.startswith("$")}
        return self.get_response_with_command(f"```{yaml.dump(json_schema, indent=2)}```")

    async def handle(self) -> Response:
        logger.info(f"Handling {self._command}")

        if self._command_args and self._command_args[0] == "schema":
            return self.get_config_schema()

        if self._command_args and self._command_args[0] == "refresh":
            if not await self._bot.try_load_configurations_from_history(self._channel_id):
                return self.get_response_with_command("Invalid or missing channel configuration")

        return await self.get_configuration_link()

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {"schema": "Get the configurations schema in yaml format. /bugmaster config schema"}
