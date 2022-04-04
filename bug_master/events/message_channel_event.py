import re
from contextlib import suppress
from typing import List

from loguru import logger
from starlette.responses import JSONResponse, Response

from .. import consts
from ..bug_master_bot import BugMasterBot
from ..channel_config_handler import ChannelFileConfig
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

    async def get_channel_configuration(self, channel_name: str) -> ChannelFileConfig:
        if not self._bot.has_channel_configurations(self.channel_id):
            await self._bot.try_load_configurations_from_history(self.channel_id)

        if not self._bot.has_channel_configurations(self.channel_id):
            await self._bot.add_comment(
                self.channel_id,
                f"BugMaster configuration file on channel `{channel_name}` is invalid or missing. "
                "Please add or fix the configuration file or remove the bot.",
            )
            return None

        return self._bot.get_configuration(self._channel_id)

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

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")
        channel_name = kwargs.get("channel_info", {}).get("name", self.channel_id)

        if (res := self._neglect_event(channel_name)) is not None:
            return res

        logger.info(f"Handling event {self}")
        if (channel_config := await self.get_channel_configuration(channel_name)) is None:
            return JSONResponse({"msg": "Failure", "Code": 401})

        links = self._get_links()
        for link in links:
            if not link.startswith(ProwJobFailure.MAIN_PAGE_URL):
                logger.info(f"Skipping comment url {link}")
                continue

            await self._handle_failure_link(link, channel_config)

        return JSONResponse({"msg": "Success", "Code": 200})

    async def _handle_failure_link(self, link: str, channel_config: ChannelFileConfig):
        with suppress(IndexError):
            pj = await ProwJobFailure(link).load()
            actions = await pj.get_failure_actions(self._channel_id, channel_config)
            ignore_others = len([action for action in actions if action.ignore_others]) > 0

            logger.debug(f"Adding comments={[action.comment for action in actions]}")
            logger.debug(f"Adding reactions={[action.reaction for action in actions]}")
            await self.add_reactions([action for action in actions if action.reaction], ignore_others)
            await self.add_comments([action for action in actions if action.comment], ignore_others)
            self.add_record(pj)

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

    def _get_links(self) -> List[str]:
        urls = list()
        for block in self._data.get("blocks", []):
            for element in block.get("elements", []):
                for e in element.get("elements", []):
                    element_type = e.get("type")
                    if element_type == "link":
                        urls.append(e.get("url"))

        # If url posted as plain text - try to get url using regex
        if not urls:
            urls = [
                url
                for url in re.findall(r"https://?[\w/\-?=%.]+\.[\w/\-&?=%.]+", self._text)
                if "prow.ci.openshift.org" in url
            ]

        logger.debug(f"Found {len(urls)} urls in event {self._data}")
        return urls
