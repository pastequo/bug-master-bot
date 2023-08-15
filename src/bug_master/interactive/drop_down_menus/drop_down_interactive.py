from abc import ABC, abstractmethod
from typing import List

from bug_master.bug_master_bot import BugMasterBot
from bug_master.interactive.interactive_message import InteractiveMessage


class DropDownInteractive(InteractiveMessage, ABC):
    def __init__(self, bot: BugMasterBot) -> None:
        super().__init__(bot)
        self._elements = []

    @classmethod
    @abstractmethod
    def drop_down_title(cls) -> str:
        pass

    @classmethod
    def fallback(cls) -> str:
        return "NotImplemented"

    @classmethod
    def color(cls) -> str:
        return "#3AA3E3"

    @classmethod
    def attachment_type(cls) -> str:
        return "default"

    @classmethod
    @abstractmethod
    def callback_id(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def list_name(cls) -> str:
        pass

    @classmethod
    @abstractmethod
    def text_box_info_text(cls) -> str:
        pass

    @classmethod
    def action_type(cls) -> str:
        return "select"

    @classmethod
    async def get_drop_down(cls, next_id: str = "", **kwargs) -> List[dict]:
        next_id = next_id if not next_id else f"-{next_id}"
        return [
            {
                "text": cls.drop_down_title(),
                "fallback": cls.fallback(),
                "color": cls.color(),
                "attachment_type": cls.attachment_type(),
                "callback_id": cls.callback_id() + next_id,
                "actions": [
                    {
                        "name": cls.list_name(),
                        "text": cls.text_box_info_text(),
                        "type": cls.action_type(),
                        "options": await cls._get_options(**kwargs),
                    }
                ],
            }
        ]

    @classmethod
    def get_new_action(
        cls, name: str, text: str, type_: str = "select", options: List[str] = None
    ):
        return {
            "name": name,
            "text": text,
            "type": type_,
            "options": options if options is not None else [],
        }

    @classmethod
    @abstractmethod
    async def _get_options(cls, **kwargs) -> List[dict]:
        pass
