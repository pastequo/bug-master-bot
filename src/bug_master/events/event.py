from abc import ABC, abstractmethod

from starlette.responses import Response

from bug_master.bug_master_bot import BugMasterBot


class BaseEvent(ABC):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        self.validate_event(body)
        self._bot = bot
        self._data: dict = body.get("event")
        self._event_id = body.get("event_id")

    @classmethod
    def validate_event(cls, body: dict):
        if body.get("event", None) is None:
            raise ValueError("Can't find event in given body")

    @abstractmethod
    async def handle(self, **kwargs) -> Response:
        pass

    def is_command_message(self):
        return False


class Event(BaseEvent, ABC):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._type = self._data.get("type", None)
        self._subtype = self._data.get("subtype", "")
        self._channel_id = self._data.get("channel")
        self._user_id = self._data.get("user")

    def __str__(self):
        return f"{self._type}:{self._subtype} {self._channel_id}"

    @property
    def channel_id(self):
        return self._channel_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def type(self):
        return self._type

    async def get_channel_info(self):
        if not self._channel_id:
            return None

        return await self._bot.get_channel_info(self._channel_id)
