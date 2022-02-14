from typing import Type, Union

from ..bug_master_bot import BugMasterBot
from .apply_command import ApplyCommand
from .channel_configuration_command import ChannelConfigurationCommand
from .command import Command
from .help_command import HelpCommand
from .statistics_command import StatisticsCommand


class NotSupportedCommandError(Exception):
    def __init__(self, message, command: str = ""):
        super().__init__(self, message)
        self.command = command
        self.message = message


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
        if not command or command not in SupportedCommands.get_commands_map():
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


class SupportedCommands:
    HELP_COMMAND = "help"
    GET_CHANNEL_CONFIGURATIONS_COMMAND = "config"
    STATISTICS_COMMAND = "stats"
    APPLY_COMMAND = "apply"

    @classmethod
    def get_commands_map(cls):
        return {
            cls.GET_CHANNEL_CONFIGURATIONS_COMMAND: ChannelConfigurationCommand,
            cls.HELP_COMMAND: HelpCommand,
            cls.STATISTICS_COMMAND: StatisticsCommand,
            cls.APPLY_COMMAND: ApplyCommand,
        }
