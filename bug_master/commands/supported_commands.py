from .apply_command import ApplyCommand
from .channel_configuration_command import ChannelConfigurationCommand
from .filterby_command import FilterByCommand
from .help_command import HelpCommand
from .statistics_command import StatisticsCommand


class SupportedCommands:
    HELP_COMMAND = "help"
    GET_CHANNEL_CONFIGURATIONS_COMMAND = "config"
    STATISTICS_COMMAND = "stats"
    APPLY_COMMAND = "apply"
    FILTERBY_COMMAND = "filterby"

    __commands = {
        GET_CHANNEL_CONFIGURATIONS_COMMAND: ChannelConfigurationCommand,
        HELP_COMMAND: HelpCommand,
        STATISTICS_COMMAND: StatisticsCommand,
        APPLY_COMMAND: ApplyCommand,
        FILTERBY_COMMAND: FilterByCommand,
    }

    @classmethod
    def get_commands_map(cls):
        return {k: v for k, v in cls.__commands.items() if v.is_enabled()}

    @classmethod
    def get_disabled_commands_map(cls):
        return {k: v for k, v in cls.__commands.items() if not v.is_enabled()}


class NotSupportedCommandError(Exception):
    def __init__(self, message, command: str = ""):
        super().__init__(self, message)
        self.command = command
        self.message = message
