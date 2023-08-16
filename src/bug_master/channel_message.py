import re
from typing import List

from bug_master import consts
from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.consts import logger
from bug_master.prow_job import ProwJobFailure


class ChannelMessage:
    def __init__(self, **kwargs):
        self._type = kwargs.get("type")
        self._user = kwargs.get("user")
        self._text = kwargs.get("text")
        self._ts = kwargs.get("ts")
        self._attachments = kwargs.get("attachments")
        self._channel_id = None

        self._links = None

    @property
    def id(self):
        return self._ts

    def is_bot_name_in_message(self):
        if self._text and "bugmaster" in self._text.lower():
            return True
        return False

    def neglect_event(self, channel_name: str) -> bool:
        """ignore unwanted messages"""

        if self.is_bot_name_in_message():
            return False

        if not self._text or not self._text.replace(" ", "").startswith(consts.EVENT_FAILURE_PREFIX):
            logger.info(f"Ignoring messages that do not start with {consts.EVENT_FAILURE_PREFIX}")
            return True

        return False

    def _get_links(self) -> List[str]:
        """Get all links from a given message text"""
        pattern = r"https://?[\w/\-?=%.]+\.[\w/\-&?=%.]+"
        urls = [url for url in re.findall(pattern, self._text) if url.startswith(ProwJobFailure.MAIN_PAGE_URL)]

        logger.debug(f"Found {len(urls)} urls in message {self._text}")
        return urls

    async def get_message_actions(self, channel_config: ChannelFileConfig, filter_id: str = None):
        actions = list()

        for link in self._get_links():
            if (failure := await ProwJobFailure(link, self._ts).load()) is not None:
                actions += await failure.get_failure_actions(self._channel_id, channel_config, filter_id)

        return actions
