from typing import Type, Union, Tuple

from sqlalchemy.orm import Session

from .event import Event, MessageChannelEvent, ChannelJoinEvent, FileShareEvent
from ..bug_master_bot import BugMasterBot
from ..consts import logger


class NotEventError(Exception):
    pass


class NotSupportedEventError(Exception):
    pass


class SupportedEvents:
    MESSAGE_TYPE = "message"
    CHANNEL_JOIN_SUBTYPE = "channel_join"
    FILE_SHARE_SUBTYPE = "file_share"

    @classmethod
    def get_events_map(cls):
        return {
            (cls.MESSAGE_TYPE, ""): MessageChannelEvent,
            (cls.MESSAGE_TYPE, cls.FILE_SHARE_SUBTYPE): FileShareEvent,
            (cls.MESSAGE_TYPE, cls.CHANNEL_JOIN_SUBTYPE): ChannelJoinEvent,
        }


class EventHandler:
    def __init__(self, bot: BugMasterBot, db: Session):
        self._bot = bot
        self._db = db

    @classmethod
    def validate_event_body(cls, body: dict) -> Tuple[str, str]:
        if body.get("event", None) is None:
            raise NotEventError("Can't find event in given body")

        event = body.get("event")
        event_type = event.get("type", None), event.get("subtype", "")
        if event_type not in SupportedEvents.get_events_map().keys():
            raise NotSupportedEventError(f"Event of type {event_type} is not supported")

        return event_type

    async def get_event(self, body: dict):
        try:
            event_type, event_subtype = self.validate_event_body(body)
        except NotSupportedEventError as e:
            logger.warning(e)
            return None

        factory: Type[Event] = self.get_event_factory(event_type, event_subtype)
        return factory(body, self._bot, self._db)

    @classmethod
    def get_event_factory(cls, event_type: str, event_subtype: str) -> Union[Type[Event], None]:
        events_factory = SupportedEvents.get_events_map()
        if (event_type, event_subtype) in events_factory.keys():
            return events_factory.get((event_type, event_subtype), None)
        return None
