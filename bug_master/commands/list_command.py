import re
from enum import Enum
from typing import Dict

from starlette.responses import Response

from ..bug_master_bot import BugMasterBot
from ..utils import Utils
from .command import Command


class ListCommands(Enum):
    LIST_JOBS = "jobs"


class ListCommand(Command):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._task = None
        self._list_command = self._command_args[0]

    @classmethod
    def command(cls):
        return "list"

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {"jobs": "List all periodic available jobs from configuration file"}

    @classmethod
    def get_description(cls) -> str:
        return "List elements - currently only `/bugmaster list jobs` is supported"

    async def handle(self) -> Response:
        if self._list_command != ListCommands.LIST_JOBS.value:
            return self.get_response_with_command(f"Invalid list command. {self._list_command}: command not found...")

        if (config := self._bot.get_configuration(self._channel_id)) is None:
            config = await self._bot.get_channel_configuration(self._channel_id, self._channel_name)
            if config is None:
                return self.get_response_with_command("Invalid or missing channel configuration")

        return await self.handle_list_job_command(config)

    async def handle_list_job_command(self, config):
        response = "Available jobs status:"
        response += "```"
        for job in await Utils.get_jobs(config.prow_configurations):
            link = f"<{Utils.get_job_history_link(job)} | link>"
            response += f"{u'•'} {re.split('(?=e2e)', job).pop()} - {link}\n"

        response += "```"
        return self.get_response_with_command(response)
