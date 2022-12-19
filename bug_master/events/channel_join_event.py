from loguru import logger
from starlette.responses import JSONResponse, Response

from ..bug_master_bot import BugMasterBot
from ..events import Event


class ChannelJoinEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._channel_name = self._data.get("name")
        self._is_private = False

    @property
    def channel_id(self):
        return self._channel_id

    def _update_info(self, info: dict):
        self._channel_name = info.get("name", self._channel_name)
        self._is_private = info.get("is_private", self._is_private)

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")

        self._update_info(kwargs.get("channel_info", {}))
        return JSONResponse({"msg": "Success", "Code": 200})
