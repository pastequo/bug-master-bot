from abc import ABC, abstractmethod
from typing import List

from sqlalchemy.orm import Session

from bug_master import models
from bug_master.bug_master_bot import BugMasterBot
from bug_master.consts import logger
from bug_master.models import MessageEvent
from bug_master.prow_job import ProwJobFailure


class BaseEvent(ABC):
    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        self.validate_event(body)
        self._bot = bot
        self._db = db
        self._data: dict = body.get("event")
        self._event_id = body.get("event_id")
        self._event_time = body.get("event_time")

    @classmethod
    def validate_event(cls, body: dict):
        if body.get("event", None) is None:
            raise ValueError("Can't find event in given body")

    @abstractmethod
    async def handle(self, **kwargs) -> dict:
        pass


class Event(BaseEvent, ABC):
    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        super().__init__(body, bot, db)
        self._type = self._data.get("type", None)
        self._subtype = self._data.get("subtype", "")
        self._channel = self._data.get("channel")

    @property
    def channel(self):
        return self._channel

    @property
    def type(self):
        return self._type


class ChannelJoinEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        super().__init__(body, bot, db)
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

    async def handle(self, **kwargs) -> dict:
        self._update_info(kwargs.get("channel_info", {}))
        kwargs = {"id": self.channel_id, "name": self.channel_name, "is_private": self._is_private}
        if not models.Channel.create(self._db, **kwargs):
            logger.warning(f"Failed to create or get channel {self.channel_id} - {self.channel_name} information")
            return {"msg": "Failure", "Code": 401}

        return {"msg": "Success", "Code": 200}


class FileShareEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        super().__init__(body, bot, db)

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    async def handle(self, **kwargs) -> dict:
        if self.contain_files:
            await self._bot.refresh_configuration(self._channel, self._data.get("files", []))
        return {"msg": "Success", "Code": 200}


class UrlVerificationEvent(BaseEvent):

    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        super().__init__(body, bot, db)
        self.challenge = body.get("challenge", "")

    async def handle(self, **kwargs) -> dict:
        return {"msg": "Success", "Code": 200}

    @classmethod
    def validate_event(cls, body: dict):
        if body.get("type", None) != "url_verification":
            raise ValueError("Can't find url_verification type event")
        logger.info("Url verification validation passed")


class MessageChannelEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot, db: Session) -> None:
        super().__init__(body, bot, db)
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

    async def handle(self, **kwargs) -> dict:
        channel_name = kwargs.get("channel_info", {}).get("name", self.channel)

        # ignore messages sent by bots or retries
        if self.is_self_event:
            logger.info(
                f"Skipping event on channel {channel_name} sent by {self._bot.id}:{self._bot.name} - " f"event: {self}"
            )
            return {"msg": "Success", "Code": 200}

        if not self._bot.has_channel_configurations(self.channel):
            if await self._bot.try_load_configurations_from_history(self.channel):
                logger.info(f"Configurations loaded successfully from channel history for channel {channel_name}")

        if not self._bot.has_channel_configurations(self.channel):
            await self._bot.add_comment(
                self.channel,
                f"Missing configuration file on channel {channel_name}. "
                "Please add configuration file or remove the bot.",
            )
            return {"msg": "Failure", "Code": 401}

        logger.info(f"Handling event {self}")
        if not self._data.get("text", "").startswith(":red_jenkins_circle:"):
            logger.info("Ignoring messages that do not start with :red_jenkins_circle:")
            return {"msg": "Success", "Code": 200}

        links = self._get_links()
        for link in links:
            try:
                pj = ProwJobFailure(link, self._bot.get_configuration(self._channel))
                emoji, text = await pj.get_failure_result()
                logger.debug(f"Adding comment={text} and emoji={emoji}")
                await self.add_reaction(emoji)
                await self.add_comment(text)
                self.add_record(pj)
            except IndexError:
                return {"msg": "Failure", "Code": 401}

        return {"msg": "Success", "Code": 200}

    def add_record(self, job_failure: ProwJobFailure):

        MessageEvent.create(session=self._db, job_id=job_failure.job_id, job_name=job_failure.name, url=job_failure.url,
                            channel_id=self._channel)

    async def add_reaction(self, emoji: str):
        if emoji:
            logger.debug(f"Adding emoji in channel {self._channel} for ts {self._ts}")
            await self._bot.add_reaction(self._channel, emoji, self._ts)

    async def add_comment(self, comment: str):
        if comment:
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

        logger.debug(f"Found {len(urls)} urls in event {self._data}")
        return urls
