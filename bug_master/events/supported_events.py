from .channel_join_event import ChannelJoinEvent
from .file_events import FileChangeEvent, FileDeletedEvent, FileShareEvent
from .message_channel_event import MessageChannelEvent
from .url_verification_event import UrlVerificationEvent


class SupportedEvents:
    MESSAGE_TYPE = "message"
    URL_VERIFICATION = "url_verification"
    CHANNEL_JOIN_SUBTYPE = "channel_join"
    FILE_SHARE_SUBTYPE = "file_share"
    FILE_CHANGED_EVENT = "file_change"
    MESSAGE_DELETED_SUBTYPE = "message_deleted"
    FILE_DELETED = "file_deleted"

    @classmethod
    def get_events_map(cls):
        return {
            (cls.MESSAGE_TYPE, ""): MessageChannelEvent,
            (cls.URL_VERIFICATION, ""): UrlVerificationEvent,
            (cls.MESSAGE_TYPE, cls.FILE_SHARE_SUBTYPE): FileShareEvent,
            (cls.MESSAGE_TYPE, cls.CHANNEL_JOIN_SUBTYPE): ChannelJoinEvent,
            (cls.FILE_CHANGED_EVENT, ""): FileChangeEvent,
            (cls.FILE_DELETED, ""): FileDeletedEvent,
        }


class NotSupportedEventError(Exception):
    pass
