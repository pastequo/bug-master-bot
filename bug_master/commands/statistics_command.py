import datetime
from collections import Counter
from typing import Dict, Tuple

from loguru import logger
from starlette.responses import Response
from tabulate import tabulate

from ..bug_master_bot import BugMasterBot
from ..models import MessageEvent
from .command import Command


class StatisticsCommand(Command):
    DEFAULT_STAT_HISTORY = 3

    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._history_days = self._command_args[0] if self._command_args else self.DEFAULT_STAT_HISTORY

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {
            "<days>": "A positive number that represent the days to query by. "
            f"/bugmaster stats <days> (default={cls.DEFAULT_STAT_HISTORY})."
        }

    @classmethod
    def get_description(cls) -> str:
        return "Print statics of last x days"

    def get_stats(self, days: int) -> Tuple[str, int]:
        counter = Counter()
        today = datetime.date.today()
        start_time = today - datetime.timedelta(days=days)

        min_date = datetime.datetime.now()
        logger.info(f"Getting statistics from database for {days} days")
        for job in MessageEvent.select(channel=self._channel_id, since=start_time):
            min_date = job.time if job.time < min_date else min_date
            counter[job.job_name] += 1

        logger.info(f"Loaded {len(counter)} failures from jobs table")
        sorted_counter = [list(job) for job in counter.most_common()]
        if not sorted_counter:
            logger.info(f"No data found for command {self}")
            return "", (today - min_date.date()).days + 1

        table = str(tabulate(sorted_counter, headers=["Test Name (link)", "Failures"]))
        rows = table.split("\n")
        headers, rows_data = rows[:2], rows[2:]
        for i in range(len(rows_data)):
            job_name = sorted_counter[i][0]
            rows_data[i] = rows_data[i].replace(
                job_name, f"<{f'https://prow.ci.openshift.org/?job=*{job_name}*'} | {job_name}>"
            )

        return "\n".join(headers + rows_data), (today - min_date.date()).days + 1

    async def handle(self) -> Response:
        try:
            days = int(self._history_days)
            if days < 1:
                raise ValueError
        except ValueError:
            return self.get_response(
                f"Invalid number of history days, got `{self._history_days}`. Positive integer is required."
            )

        stats, days = self.get_stats(days)
        if not stats:
            return self.get_response(f"There are no records for this channel in the last {days} days.")
        return self.get_response(f"Statistics for the last {days} days:\n```{stats}```")
