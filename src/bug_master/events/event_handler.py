from typing import Tuple, Type, Union

from bug_master.bug_master_bot import BugMasterBot
from bug_master.consts import logger
from bug_master.events.event import Event
from bug_master.events.supported_events import NotSupportedEventError, SupportedEvents


class NotEventError(Exception):
    pass


class EventHandler:
    def __init__(self, bot: BugMasterBot):
        self._bot = bot

    @classmethod
    def validate_event_body(cls, body: dict) -> Tuple[str, str]:
        if "type" in body and body["type"] == "url_verification":
            return "url_verification", ""

        if body.get("event", None) is None:
            raise NotEventError("Can't find event in given body")

        event = body.get("event")
        if event.get("thread_ts"):
            raise NotSupportedEventError(
                "Event of type thread comment is not supported"
            )

        event_type = event.get("type", None), event.get("subtype", "")
        if event_type not in SupportedEvents.get_events_map().keys():
            raise NotSupportedEventError(f"Event of type {event_type} is not supported")

        logger.info(f"New event arrived - {event_type}")
        return event_type

    async def get_event(self, body: dict) -> Union[Event, None]:
        try:
            event_type, event_subtype = self.validate_event_body(body)
        except NotSupportedEventError as e:
            logger.warning(e)
            return None

        factory: Type[Event] = self.get_event_factory(event_type, event_subtype)
        return factory(body, self._bot)

    @classmethod
    def get_event_factory(
        cls, event_type: str, event_subtype: str
    ) -> Union[Type[Event], None]:
        events_factory = SupportedEvents.get_events_map()
        if (event_type, event_subtype) in events_factory.keys():
            return events_factory.get((event_type, event_subtype), None)
        return None
