from loguru import logger
from starlette.responses import JSONResponse, Response

from bug_master.bug_master_bot import BugMasterBot
from bug_master.events.event import BaseEvent


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
