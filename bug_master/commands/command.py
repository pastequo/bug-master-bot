import datetime
import re
from abc import ABC, abstractmethod
from collections import Counter
from typing import Dict, List, Tuple

from starlette.responses import JSONResponse, Response

from bug_master.bug_master_bot import BugMasterBot

from .. import consts
from ..consts import logger
from ..models import MessageEvent


class SupportedCommands:
    HELP_COMMAND = "help"
    GET_CHANNEL_CONFIGURATIONS_COMMAND = "config"
    STATISTICS_COMMAND = "stats"

    @classmethod
    def get_commands_map(cls):
        return {
            cls.GET_CHANNEL_CONFIGURATIONS_COMMAND: GetChannelConfigurationCommand,
            cls.HELP_COMMAND: HelpCommand,
            cls.STATISTICS_COMMAND: StatisticsCommand,
        }


class NotSupportedCommandError(Exception):
    pass


class Command(ABC):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        self._bot = bot
        self._channel_id = kwargs.get("channel_id")
        self._channel_name = kwargs.get("channel_name")
        self._command, self._command_args = self.get_command(kwargs.get("text"))

    @classmethod
    def get_command(cls, text: str) -> Tuple[str, List[str]]:
        code_blocks = re.findall(r"```(\n|-[\s\S]*?)```$", text)
        if code_blocks:
            text = text.replace(code_blocks[0], "")

        command, *args = re.findall(r"[a-zA-Z0-9]+", text)
        if code_blocks:
            args += code_blocks
        return command, args

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        pass

    @abstractmethod
    async def handle(self) -> Dict[str, str]:
        pass

    @classmethod
    def get_response(cls, text: str) -> Response:
        return JSONResponse({"response_type": "ephemeral", "text": text})


class GetChannelConfigurationCommand(Command):
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


class StatisticsCommand(Command):
    DEFAULT_STAT_HISTORY = 10

    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._history_days = self._command_args[0] if self._command_args else self.DEFAULT_STAT_HISTORY

    @classmethod
    def get_description(cls) -> str:
        return "Print statics of last x days. Command: /bugmaster stats <integer> (default=10)."

    def get_stats(self, days: int) -> str:
        counter = Counter()
        res = []

        start_time = datetime.date.today() - datetime.timedelta(days=days)

        for job in MessageEvent.select(channel=self._channel_id, since=start_time):
            counter[job.job_name] += 1

        jobs = list(counter.keys())
        counts = list(counter.values())
        for i in range(len(jobs)):
            res.append(f" {i+1}. {jobs[i]} -> {counts[i]} failures")

        return "\n".join(res)

    async def handle(self) -> Response:
        try:
            days = int(self._history_days)
            if days < 1:
                raise ValueError
        except ValueError:
            return self.get_response(
                f"Invalid number of history days, got `{self._history_days}`. Positive integer is required."
            )

        stats = self.get_stats(days)
        if not stats:
            return self.get_response(f"There are no records for this channel in the last {days} days.")
        return self.get_response(f"Statistics for the last {days} days:\n```{stats}```")


class HelpCommand(Command):
    @classmethod
    def get_description(cls) -> str:
        return "More information about how to use Bot Master"

    @classmethod
    def get_commands_info(cls) -> str:
        commands_map = SupportedCommands.get_commands_map()
        commands = list(commands_map.keys())
        commands_cls = list(commands_map.values())
        commands_info = "\n".join(
            [f"{i + 1}. {commands[i]} - {commands_cls[i].get_description()}" for i in range(len(commands))]
        )
        return commands_info

    async def handle(self) -> Response:
        logger.info(f"Handling {self._command}")

        return self.get_response(
            f"*============== Help ==============*\n"
            f"*Available commands:*\n"
            f"```{self.get_commands_info()}```\n\n"
            f"*Configuration file:*\n"
            f"Bot configuration file, defines each job action on failure. The configuration file name must be named"
            f" `{consts.CONFIGURATION_FILE_NAME}`.\n"
            f"For each section (job failure) this are the following arguments:\n"
            f"``` 1. description  - Description of the failure.\n"
            f" 2. emoji - Reaction to add to the thread on case of match (If empty or missing no reaction "
            f"is posted).\n"
            f" 3. text -  Comment to add to thread on case of match (If empty or missing, no comment is posted)\n"
            f" 4. contains - String that indicates the failure, checks if any files content that listed on "
            f"`file_path` contains that given string.\n"
            f" 6. file_path  - File or directory to search for match in it. The path is relative to PROW job"
            f" (starting with artifacts). To specify a directory just set file name to be *.```\n"
        )
