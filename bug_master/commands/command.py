import re
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

from starlette.responses import JSONResponse, Response

from ..bug_master_bot import BugMasterBot


class Command(ABC):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        self._bot = bot
        self._channel_id = kwargs.get("channel_id")
        self._user_id = kwargs.get("user_id")
        self._user_name = kwargs.get("user_name")
        self._channel_name = kwargs.get("channel_name")
        self._command, self._command_args = self.get_command(kwargs.get("text"))

    def __str__(self):
        return f"{self._command}, {self._channel_name}"

    @classmethod
    @abstractmethod
    def command(cls):
        pass

    @property
    def user_id(self):
        return self._user_id

    @classmethod
    def is_enabled(cls):
        return True

    @classmethod
    def get_command(cls, text: str) -> Tuple[str, List[str]]:
        code_blocks = re.findall(r"```(\n|-[\s\S]*?)```$", text)
        if code_blocks:
            text = text.replace(code_blocks[0], "")

        command, *args = re.findall(r"[a-zA-Z0-9]+", text)
        if code_blocks:
            args += code_blocks
        return command, args

    @classmethod
    @abstractmethod
    def get_description(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        pass

    @abstractmethod
    async def handle(self) -> Response:
        pass

    def get_response_with_command(self, text: str) -> Response:
        text = f"```$ /bugmaster {self.command()} {' '.join(self._command_args)}```\n" + text
        return JSONResponse({"response_type": "ephemeral", "text": text})

    @classmethod
    def get_response(cls, text: str) -> Response:
        return JSONResponse({"response_type": "ephemeral", "text": text})
