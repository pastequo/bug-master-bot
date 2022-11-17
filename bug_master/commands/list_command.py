import asyncio
import datetime
import re
from enum import Enum
from typing import Dict, List, Tuple

from starlette.responses import Response
from tabulate import tabulate

from ..bug_master_bot import BugMasterBot
from ..utils import Utils
from .command import Command
from .exceptions import NotSupportedCommandError


class ListCommands(Enum):
    LIST_JOBS = "jobs"


class ListCommand(Command):
    WEEK = 7

    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._task = None
        if len(self._command_args) < 1:
            raise NotSupportedCommandError(f"Command is not supported")
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
        asyncio.get_event_loop().create_task(self._handle_jobs_history_report(config))
        return self.get_response_with_command("Loading jobs list...")

    async def _handle_jobs_history_report(self, config, days: int = WEEK):
        tasks = []
        results = []

        for job in await Utils.get_jobs(config.prow_configurations):
            tasks.append(asyncio.get_event_loop().create_task(self._load_job_history_data(results, job, days)))

        while True:
            if all([task.done() for task in tasks]):
                break
            await asyncio.sleep(2)

        table = self._get_list_jobs_success_rate_table(results)
        comment = f"Jobs list report for the last {days} days:\n```{table}```"
        await self._bot.add_ephemeral_comment(self._channel_id, self._user_id, comment)

    @classmethod
    def _get_list_jobs_success_rate_table(cls, results: List[Tuple[str, int, int]]) -> str:
        jobs_data = []
        if not results:
            return "Can't find any jobs"

        for job_name, total_jobs, succeeded_jobs in results:
            if total_jobs == 0 or total_jobs == succeeded_jobs:
                continue

            short_job_name = f"{re.split('(?=e2e)', job_name).pop().replace('-periodic', '')}"
            success_rate = 100 * (succeeded_jobs / total_jobs)
            jobs_data.append(
                (short_job_name, f"{success_rate:.2f}% ({succeeded_jobs}/{total_jobs})", success_rate, job_name)
            )

        jobs_data.sort(key=lambda data: data[2], reverse=True)

        # Remove columns needed only as local data
        table = tabulate([d[:-2] for d in jobs_data], headers=["Job Name", "Success rate"], tablefmt="rounded_outline")
        return cls._align_list_jobs_table_link_chars(table, jobs_data)

    @classmethod
    def _align_list_jobs_table_link_chars(cls, table: str, jobs_data: List):
        rows = table.split("\n")
        headers, rows_data = rows[:2], rows[2:]

        jobs_data_index = 0  # handle different table formats
        for i in range(len(rows_data)):
            if "e2e" not in rows_data[i]:
                continue

            short_job_name = jobs_data[jobs_data_index][0]
            link = (
                f"<{Utils.get_job_history_link(jobs_data[jobs_data_index][3])} | "
                f"{re.split('(?=e2e)', short_job_name).pop().replace('-periodic', '')}>"
            )
            rows_data[i] = rows_data[i].replace(short_job_name, link)
            jobs_data_index += 1

        return "\n".join(headers + rows_data)

    @classmethod
    async def _load_job_history_data(cls, result: List[Tuple[str, int, int]], job_name: str, days: int):
        date = (datetime.datetime.now() - datetime.timedelta(days=days)).date()

        jobs = []
        for job_status in await Utils.get_job_history(job_name):
            if date <= job_status.started.date():
                jobs.append(job_status)

        succeeded_jobs = [j for j in jobs if j.succeeded]
        result.append((job_name, len(jobs), len(succeeded_jobs)))
