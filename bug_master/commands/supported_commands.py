from .apply_command import ApplyCommand
from .channel_configuration_command import ChannelConfigurationCommand
from .filterby_command import FilterByCommand
from .help_command import HelpCommand
from .job_info_command import JobInfoCommand
from .list_command import ListCommand
from .statistics_command import StatisticsCommand


class SupportedCommands:
    _commands = {
        ChannelConfigurationCommand.command(): ChannelConfigurationCommand,
        HelpCommand.command(): HelpCommand,
        StatisticsCommand.command(): StatisticsCommand,
        ApplyCommand.command(): ApplyCommand,
        FilterByCommand.command(): FilterByCommand,
        JobInfoCommand.command(): JobInfoCommand,
        ListCommand.command(): ListCommand,
    }

    @classmethod
    def get_commands_map(cls):
        return {k: v for k, v in cls._commands.items() if v.is_enabled()}

    @classmethod
    def get_disabled_commands_map(cls):
        return {k: v for k, v in cls._commands.items() if not v.is_enabled()}
