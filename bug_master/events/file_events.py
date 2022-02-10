from loguru import logger
from starlette.responses import JSONResponse, Response

from ..bug_master_bot import BugMasterBot
from ..consts import CONFIGURATION_FILE_NAME
from ..events import Event


class FileShareEvent(Event):
    def __init__(self, body: dict, bot: BugMasterBot) -> None:
        super().__init__(body, bot)

    @property
    def contain_files(self):
        return self._data and self._data.get("files")

    async def handle(self, **kwargs) -> Response:
        logger.info(f"Handling {self.type}, {self._subtype} event")

        if self.contain_files:
            await self._bot.refresh_file_configuration(self._channel, self._data.get("files", []))
        return JSONResponse({"msg": "Success", "Code": 200})


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
            await self._bot.refresh_file_configuration(self._channel, [file_info])
        return JSONResponse({"msg": "Success", "Code": 200})
