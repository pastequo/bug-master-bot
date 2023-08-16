from loguru import logger
from starlette.responses import JSONResponse, Response

from bug_master.bug_master_bot import BugMasterBot
from bug_master.consts import CONFIGURATION_FILE_NAME
from bug_master.events import Event


class FileShareEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")

        if self.contain_files:
            await self._bot.refresh_file_configuration(self._channel_id, self._data.get("files", []), force_create=True)
        return JSONResponse({"msg": "Success", "Code": 200})


class FileChangeEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._file_id = self._data.get("file_id")
        self._user_id = self._data.get("user_id")
        self._file_info = {}

    async def get_file_info(self):
        if self._file_info:
            return self._file_info
        self._file_info = await self._bot.get_file_info(self._file_id)
        return self._file_info

    async def _update_channel_info(self):
        file_info = await self.get_file_info()
        channels = file_info.get("channels")
        self._channel_id = channels[0]

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
            await self._bot.refresh_file_configuration(self._channel_id, [file_info], user_id=self._user_id)

        return JSONResponse({"msg": "Success", "Code": 200})


class FileDeletedEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)
        self._channels = set(self._data.get("channel_ids"))
        self._channel_id = list(self._channels)[0] if len(self._channels) > 0 else ""
        self._file_id = self._data.get("file_id")

    async def handle(self, **kwargs) -> Response:
        for channel_id in self._channels:
            self._bot.reset_configuration(channel_id)

        return JSONResponse({"msg": "Success", "Code": 200})
