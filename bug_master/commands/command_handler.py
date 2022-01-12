from typing import Type, Union

from ..bug_master_bot import BugMasterBot
from ..consts import logger
from .command import Command, GetChannelCommand


class NotSupportedCommandError(Exception):
    pass


class SupportedCommands:
    GET_CHANNEL_CONFIGURATIONS = "config"

    @classmethod
    def get_commands_map(cls):
        return {cls.GET_CHANNEL_CONFIGURATIONS: GetChannelCommand}


class CommandHandler:
    def __init__(self, bot: BugMasterBot):
        self._bot = bot

    @classmethod
    def validate_command_body(cls, body: dict) -> str:
        command = body.get("text")
        if not command or command not in SupportedCommands.get_commands_map():
            raise NotSupportedCommandError(f"Command of type `{command}` is not supported")
        return command

    async def get_command(self, body: dict) -> Union[Command, None]:
        try:
            command = self.validate_command_body(body)
        except NotSupportedCommandError as e:
            logger.warning(e)
            raise

        factory: Type[Command] = self.get_factory(command)
        return factory(self._bot, **body)

    @classmethod
    def get_factory(cls, command_key: str) -> Union[Type[Command], None]:
        commands_factory = SupportedCommands.get_commands_map()
        if command_key in commands_factory.keys():
            return commands_factory.get(command_key, None)
        return None
