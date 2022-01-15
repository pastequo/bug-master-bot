import re
from abc import ABC, abstractmethod
from typing import List

from starlette.responses import JSONResponse, Response

from bug_master import models
from bug_master.bug_master_bot import BugMasterBot
from bug_master.consts import CONFIGURATION_FILE_NAME, logger
from bug_master.models import MessageEvent
from bug_master.prow_job import ProwJobFailure


class BaseEvent(ABC):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        self.validate_event(body)
        self._bot = bot
        self._data: dict = body.get("event")
        self._event_id = body.get("event_id")
        self._event_time = body.get("event_time")

    @classmethod
    def validate_event(cls, body: dict):
        if body.get("event", None) is None:
            raise ValueError("Can't find event in given body")

    @abstractmethod
    async def handle(self, **kwargs) -> Response:
        pass


class Event(BaseEvent, ABC):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._type = self._data.get("type", None)
        self._subtype = self._data.get("subtype", "")
        self._channel = self._data.get("channel")

    @property
    def channel(self):
        return self._channel

    @property
    def type(self):
        return self._type

    async def get_channel_info(self):
        return await self._bot.get_channel_info(self._channel)


class ChannelJoinEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._channel_id = self._data.get("channel")
        self._channel_name = self._data.get("name")
        self._is_private = False

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def channel_name(self):
        return self._channel_name

    def _update_info(self, info: dict):
        self._channel_name = info.get("name", self._channel_name)
        self._is_private = info.get("is_private", self._is_private)

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")

        self._update_info(kwargs.get("channel_info", {}))
        kwargs = {"id": self.channel_id, "name": self.channel_name, "is_private": self._is_private}
        if not models.Channel.create(**kwargs):
            logger.warning(f"Failed to create or get channel {self.channel_id} - {self.channel_name} information")
            return JSONResponse({"msg": "Failure", "Code": 401})

        return JSONResponse({"msg": "Success", "Code": 200})


class FileShareEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")

        if self.contain_files:
            await self._bot.refresh_configuration(self._channel, self._data.get("files", []))
        return JSONResponse({"msg": "Success", "Code": 200})


class UrlVerificationEvent(BaseEvent):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self.challenge = body.get("challenge", "")

    async def handle(self, **kwargs) -> Response:
        return JSONResponse({"msg": "Success", "Code": 200})

    @classmethod
    def validate_event(cls, body: dict):
        if body.get("type", None) != "url_verification":
            raise ValueError("Can't find url_verification type event")
        logger.info("Url verification validation passed")


class MessageChannelEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._msg_id = self._data.get("client_msg_id")
        self._user = self._data.get("user")
        self._channel_type = self._data.get("channel_type")
        self._text = self._data.get("text")
        self._ts = self._data.get("ts")

    def __str__(self):
        return (
            f"id: {self._event_id}, time: {self._event_time}, user: {self._user}, "
            f"channel: {self._channel} ts: {self._ts}, has_file: {self.contain_files}"
        )

    @property
    def channel(self) -> str:
        return self._channel

    @property
    def user(self) -> str:
        return self._user

    @property
    def is_self_event(self) -> bool:
        if "bot_id" in self._data:
            if self._bot.id == self._data.get("bot_id"):
                return True
        return False

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")
        channel_name = kwargs.get("channel_info", {}).get("name", self.channel)

        # ignore messages sent by bots or retries
        if self.is_self_event:
            logger.info(
                f"Skipping event on channel {channel_name} sent by {self._bot.id}:{self._bot.name} - " f"event: {self}"
            )
            return JSONResponse({"msg": "Success", "Code": 200})

        if not self._bot.has_channel_configurations(self.channel):
            await self._bot.try_load_configurations_from_history(self.channel)

        if not self._bot.has_channel_configurations(self.channel):
            await self._bot.add_comment(
                self.channel,
                f"Missing configuration file on channel {channel_name}. "
                "Please add configuration file or remove the bot.",
            )
            return JSONResponse({"msg": "Failure", "Code": 401})

        logger.info(f"Handling event {self}")
        if not self._data.get("text", "").replace(" ", "").startswith(":red_jenkins_circle:"):
            logger.info("Ignoring messages that do not start with :red_jenkins_circle:")
            return JSONResponse({"msg": "Success", "Code": 200})

        links = self._get_links()
        for link in links:
            try:
                pj = ProwJobFailure(link)
                emojis, texts = await pj.get_failure_actions(self._bot.get_configuration(self._channel))
                logger.debug(f"Adding comments={texts} and emojis={emojis}")
                await self.add_reactions(emojis)
                await self.add_comments(texts)
                self.add_record(pj)
            except IndexError:
                continue

        return JSONResponse({"msg": "Success", "Code": 200})

    def add_record(self, job_failure: ProwJobFailure):
        MessageEvent.create(
            job_id=job_failure.job_id,
            job_name=job_failure.name,
            user=self._user,
            thread_ts=self._ts,
            url=job_failure.url,
            channel_id=self._channel,
        )

    async def add_reactions(self, emojis: List[str]):
        for emoji in emojis:
            logger.debug(f"Adding reactions to channel {self._channel} for ts {self._ts}")
            await self._bot.add_reaction(self._channel, emoji, self._ts)

    async def add_comments(self, comments: List[str]):
        for comment in comments:
            logger.debug(f"Adding comment in channel {self._channel} for ts {self._ts}")
            await self._bot.add_comment(self._channel, comment, self._ts)

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


class FileChangeEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._file_id = self._data.get("file_id")
        self._file_info = {}

    async def get_file_info(self):
        if self._file_info:
            return self._file_info
        self._file_info = await self._bot.get_file_info(self._file_id)
        return self._file_info

    async def _update_channel_info(self):
        file_info = await self.get_file_info()
        channels = file_info.get("channels")
        self._channel = channels[0]

    async def get_channel_info(self):
        try:
            await self._update_channel_info()
            return await super().get_channel_info()
        except IndexError as e:
            logger.warning(f"Error while attempt to get channel info in {self._type}:{self._subtype}, {e}")

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")
        file_info = await self.get_file_info()
        if file_info.get("title", "") == CONFIGURATION_FILE_NAME:
            await self._bot.refresh_configuration(self._channel, [file_info])
        return JSONResponse({"msg": "Success", "Code": 200})
