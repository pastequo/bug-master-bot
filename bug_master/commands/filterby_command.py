import asyncio
import time
from builtins import list
from itertools import chain
from typing import Dict

from starlette.responses import Response

from ..async_pool import AsyncPool
from ..bug_master_bot import BugMasterBot
from ..channel_config_handler import ChannelFileConfig
from ..channel_message import ChannelMessage
from .command import Command


class FilterByCommand(Command):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._days, self._action_id = self._command_args

    @classmethod
    def get_description(cls) -> str:
        return "Filter failed jobs by given conditions"

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {
            "<days>": "A positive number that represent the days to query by",
            "action_id": "A unique ID from the channel configuration file /bugmaster filterby <days> <action_id>",
        }

    async def handle(self) -> Response:
        channel_info = await self._bot.get_channel_info(self._channel_id) if self._channel_id else {}
        channel_name = channel_info.get("name", self._channel_id)

        if (channel_config := await self._bot.get_channel_configuration(self._channel_id, channel_name)) is None:
            return self.get_response("Can't find channel configurations or that the configurations are not valid")

        asyncio.get_event_loop().create_task(self._handle_messages(channel_config))

        return self.get_response(
            "Task is being executed in the background and it might take some time to finish the report. The result will"
            "be sent as a private message."
        )

    async def _handle_messages(self, channel_config: ChannelFileConfig):
        since = int(time.time()) - (int(self._days) * 24 * 60 * 60)
        actions = await self._get_actions(since, channel_config)

        # Create report
        message = (
            f"Hi {self._user_name},\n The error with `action_id={self._action_id}` has appeared {len(actions)} "
            f"times in the last {self._days} days"
        )

        await self._bot.add_comment(channel=self._user_id, comment=message)

    async def _get_actions(self, since: float, channel_config: ChannelFileConfig):
        messages_data = await self._bot.get_all_messages(self._channel_id, since)

        pool = AsyncPool(10)
        messages = list()
        for message_data in messages_data:
            message = ChannelMessage(**message_data)
            await pool.add_worker(
                message.id, message.get_message_actions, channel_config=channel_config, filter_id=self._action_id
            )
            messages.append(message)

        actions_map = await pool.start()
        return list(chain(*[action for action in actions_map for ts, action in action.items() if action]))

    async def _get_message_actions(self, message: ChannelMessage, channel_config: ChannelFileConfig):
        return await message.get_message_actions(channel_config, self._action_id)
