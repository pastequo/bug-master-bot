from typing import Type, Union

from ..bug_master_bot import BugMasterBot
from .command import Command
from .exceptions import NotSupportedCommandError
from .help_command import HelpCommand
from .supported_commands import SupportedCommands


class CommandHandler:
    def __init__(self, bot: BugMasterBot):
        self._bot = bot

    @classmethod
    def validate_command_body(cls, body: dict) -> str:
        if body.get("text") is None:
            raise NotSupportedCommandError(
                "Hello, How can I help you? For more info you can" " always write `/bugmaster help`.",
                command="",
            )
        command, _ = Command.get_command(body.get("text"))
        supported_commands = SupportedCommands.get_commands_map()
        if not command or command not in supported_commands or not supported_commands.get(command).is_enabled():
            raise NotSupportedCommandError(
                f"Command `{command}` is not supported. Available commands:\n"
                f"```{HelpCommand.get_commands_info()}```",
                command=command,
            )
        return command

    async def get_command(self, body: dict) -> Union[Command, None]:
        """:raise NotSupportedCommandError"""
        command = self.validate_command_body(body)

        factory: Type[Command] = self.get_factory(command)
        return factory(self._bot, **body)

    @classmethod
    def get_factory(cls, command_key: str) -> Union[Type[Command], None]:
        commands_factory = SupportedCommands.get_commands_map()
        if command_key in commands_factory.keys():
            return commands_factory.get(command_key, None)
        return None
