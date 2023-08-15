from bug_master.commands.apply_command import ApplyCommand
from bug_master.commands.channel_configuration_command import (
    ChannelConfigurationCommand,
)
from bug_master.commands.filterby_command import FilterByCommand
from bug_master.commands.help_command import HelpCommand
from bug_master.commands.job_info_command import JobInfoCommand
from bug_master.commands.list_command import ListCommand
from bug_master.commands.statistics_command import StatisticsCommand


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
