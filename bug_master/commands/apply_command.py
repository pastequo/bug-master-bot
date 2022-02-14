import asyncio
from typing import List, Dict

from loguru import logger
from starlette.responses import Response

from .. import consts
from ..bug_master_bot import BugMasterBot
from ..events.message_channel_event import MessageChannelEvent
from .command import Command


class ApplyCommand(Command):
    DEFAULT_HISTORY_MESSAGES_TO_READ = 20
    MAX_HISTORY_MESSAGES_TO_READ = 200

    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._task = None

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {"<messages>": "A positive number that represent the amount of messages to apply on. "
                              f"/bugmaster apply <messages> (default={cls.DEFAULT_HISTORY_MESSAGES_TO_READ})."}

    @classmethod
    def get_description(cls) -> str:
        return "Apply BugMasterBot logic on n last channel messages"

    def _get_messages_count(self):
        if not self._command_args or not self._command_args[0]:
            return self.DEFAULT_HISTORY_MESSAGES_TO_READ

        messages_count = int(self._command_args[0])
        if messages_count < 1:
            raise ValueError

        return min(messages_count, self.MAX_HISTORY_MESSAGES_TO_READ)

    async def handle(self) -> Response:
        try:
            messages_count = self._get_messages_count()
        except ValueError:
            return self.get_response(
                f"Invalid number of messages to read, got `{self._command_args[0]}`. Positive integer is required."
            )
        messages, _cursor = await self._bot.get_messages(self._channel_id, messages_count)
        logger.info(f"Got {len(messages)} form channel {self._channel_id}:{self._channel_name}, creating task ...")
        self._task = asyncio.get_event_loop().create_task(self.update_task(messages))
        return self.get_response(
            f"Updating process is in progress, this might take a few minutes to finish.\n"
            f"`Messages loaded from history: {len(messages)}`"
        )

    def _is_already_handled(self, message: dict) -> bool:
        for reaction in message.get("reactions", []):
            if self._bot.user_id in reaction.get("users", []):
                return True

        if self._bot.user_id in message.get("reply_users", []):
            return True

        return False

    async def update_task(self, messages: List[dict]):
        tasks = []

        for message in messages:
            if not message.get("text", "").strip().startswith(consts.EVENT_FAILURE_PREFIX):
                logger.debug(
                    f"Skipping message due to it's not starting with {consts.EVENT_FAILURE_PREFIX} "
                    f"{message['text']}"
                )
                continue

            if self._is_already_handled(message):
                logger.debug(f"Skipping message due to it was already handled\n{message}")
                continue

            logger.info(f"Handling unhandled message {message}")

            # todo create shared base code with MessageChannelEvent and this class and not reuse the event mechanism
            dummy_event_body = {
                "event": {
                    "type": "not_an_event_history_apply_task",
                    "channel": self._channel_id,
                    "text": message["text"],
                    "ts": message["ts"],
                    "user": message["user"],
                },
                "event_id": message["ts"],
            }
            mce = MessageChannelEvent(dummy_event_body, self._bot)
            channel_info = await mce.get_channel_info()

            await asyncio.sleep(1)
            task = asyncio.get_event_loop().create_task(mce.handle(channel_info=channel_info))
            tasks.append(task)

        logger.info(f"Waiting for {len(tasks)} background tasks to finish.")

        while True:
            if all([task.done() for task in tasks]):
                break
            await asyncio.sleep(2)

        logger.info(
            f"Finished background task for handling {len(messages)} messages. " f"Total actions needed {len(tasks)}."
        )
