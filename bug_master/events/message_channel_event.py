from contextlib import suppress
from typing import List

from starlette.responses import JSONResponse, Response

from .. import consts
from ..bug_master_bot import BugMasterBot
from ..channel_config_handler import ChannelFileConfig
from ..channel_message import ChannelMessage
from ..consts import logger
from ..entities import Action
from ..models import MessageEvent
from ..prow_job import ProwJobFailure
from .event import Event


class MessageChannelEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._user = self._data.get("user")
        self._text = self._data.get("text")
        self._ts = self._data.get("ts")
        self._message = ChannelMessage(**self._data)

    def __str__(self):
        return (
            f"id: {self._event_id}, user: {self._user}, channel: {self._channel_id} ts: {self._ts},"
            f" has_file: {self.contain_files}"
        )

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def user(self) -> str:
        return self._user

    @property
    def is_self_event(self) -> bool:
        if "bot_id" in self._data:
            if self._bot.bot_id == self._data.get("bot_id"):
                return True
        return False

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    def is_command_message(self):
        return self._text and self._text.startswith("/bugmaster")

    def _neglect_event(self, channel_name: str):
        # ignore messages sent by bots or retries
        if self.is_self_event:
            logger.info(
                f"Skipping event on channel {channel_name} sent by {self._bot.bot_id}:{self._bot.name} - "
                f"event: {self}"
            )
            return JSONResponse({"msg": "Success", "Code": 200})

        if not self._data.get("text", "").replace(" ", "").startswith(consts.EVENT_FAILURE_PREFIX):
            logger.info(f"Ignoring messages that do not start with {consts.EVENT_FAILURE_PREFIX}")
            return JSONResponse({"msg": "Success", "Code": 200})

        return None

    async def skip_event(self, channel_name: str):
        if self.is_self_event:
            logger.info(f"Skipping event on {channel_name} sent by {self._bot.bot_id}:{self._bot.name} - {self}")
            return True

        if self._message.neglect_event(channel_name):
            return True

        return False

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")
        channel_name = kwargs.get("channel_info", {}).get("name", self.channel_id)

        if await self.skip_event(channel_name):
            return JSONResponse({"msg": "Success", "Code": 200})

        logger.info(f"Handling event {self}")
        if (channel_config := await self._bot.get_channel_configuration(self._channel_id, channel_name)) is None:
            return JSONResponse({"msg": "Failure", "Code": 401})

        await self._handle_failure_actions(channel_config)
        return JSONResponse({"msg": "Success", "Code": 200})

    async def _handle_failure_actions(self, channel_config: ChannelFileConfig):
        with suppress(IndexError):
            actions = await self._message.get_message_actions(channel_config)
            ignore_others = len([action for action in actions if action.ignore_others]) > 0
            logger.debug(f"Adding comments={[action.comment for action in actions]}")
            logger.debug(f"Adding reactions={[action.reaction for action in actions]}")
            await self.add_reactions([action for action in actions if action.reaction], ignore_others)
            await self.add_comments([action for action in actions if action.comment], ignore_others)
            # self.add_record(pj)  # todo need to fix database behavior

    def add_record(self, job_failure: ProwJobFailure):
        MessageEvent.create(
            job_id=job_failure.build_id,
            job_name=job_failure.job_name,
            user=self._user,
            thread_ts=self._ts,
            url=job_failure.url,
            channel_id=self._channel_id,
        )

    @classmethod
    def filter_ignore_others(cls, actions: List[Action], ignore_others: bool = False):
        prioritized = [action for action in actions if action.ignore_others]
        return prioritized if ignore_others else actions

    async def add_reactions(self, actions: List[Action], ignore_others: bool = False):
        for action in self.filter_ignore_others(actions, ignore_others):
            logger.debug(f"Adding reactions to channel {self._channel_id} for ts {self._ts}")
            await self._bot.add_reaction(self._channel_id, action.reaction.emoji, self._ts)

    async def add_comments(self, actions: List[Action], ignore_others: bool = False):
        for action in sorted(
            self.filter_ignore_others(actions, ignore_others), key=lambda a: a.comment.type.value, reverse=True
        ):
            logger.debug(f"Adding comment in channel {self._channel_id} for ts {self._ts}")
            await self._bot.add_comment(self._channel_id, action.comment.text, self._ts, action.comment.parse)
