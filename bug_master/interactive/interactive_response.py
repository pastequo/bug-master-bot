import datetime
import re

from starlette.responses import JSONResponse

from bug_master.bug_master_bot import BugMasterBot
from bug_master.interactive.interactive_flow_handler import InteractiveFlowHandler
from bug_master.utils import Utils


class InteractiveResponse:
    def __init__(self, bot: BugMasterBot, payload: dict) -> None:
        self._bot = bot
        self._type = payload.get("type")
        self._message_ts = payload.get("message_ts")
        self._action_ts = payload.get("action_ts")
        self._channel_id = payload.get("channel", {}).get("id")
        self._actions = payload.get("actions", [])
        self._original_message = payload.get("original_message", {})
        self._callback_id = payload.get("callback_id", "")
        self._payload = payload

    @property
    def original_message(self):
        return self._original_message

    @property
    def actions(self):
        return self._actions

    async def get_next_response(self) -> JSONResponse:
        callback_ids = self._callback_id.split("-")
        next_message = self._original_message

        if len(callback_ids) > 1:
            next_callback_id = callback_ids[1]
            job_name = self._actions[0].get("selected_options")[0].get("value")
            attachments = await InteractiveFlowHandler.get_next(next_callback_id).get_drop_down(job_name=job_name)
            next_message["attachments"] = attachments
            return JSONResponse(next_message)

        return JSONResponse({"text": await self._get_final_response()})

    async def _get_final_response(self):
        selected_items = self._actions[0].get("selected_options")[0].get("value").split("|")
        days, job_name = int(selected_items[0]), selected_items[1]
        jobs_history = await Utils.get_jobs_history(job_name)
        date = (datetime.datetime.now() - datetime.timedelta(days=days)).date()

        jobs = []
        for job in jobs_history:
            if date <= job.started.date():
                jobs.append(job)

        failed_jobs = [j for j in jobs if not j.succeeded]
        succeeded_jobs = [j for j in jobs if j.succeeded]
        success_rate = 100 * len(succeeded_jobs) / (len(jobs))
        msg = "```"
        msg += ("=" * 8) + f" {re.split('(?=e2e)', job_name).pop()} " + ("=" * 8) + "\n"
        msg += (
            f" {u'•'} Total jobs failed since {date}: {len(failed_jobs)}\n"
            f" {u'•'} Total jobs succeeded since {date}: {len(succeeded_jobs)}\n"
            f" {u'•'} Success rate: {success_rate:.2f}%\n\n"
            f" Job history can be found here - <{Utils.SPYGLASS_JOB_HISTORY_URL_FMT.format(JOB_NAME=job_name)} | link>"
        )
        msg += "```"

        return msg
