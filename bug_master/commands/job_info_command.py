import asyncio
from typing import Dict

from loguru import logger
from starlette.responses import Response

from ..bug_master_bot import BugMasterBot
from ..interactive import DaysRangeDropDown, JobsDropDown
from ..models.channel_config import ChannelConfig
from .command import Command


class JobInfoCommand(Command):
    def __init__(self, bot: BugMasterBot, **kwargs) -> None:
        super().__init__(bot, **kwargs)
        self._task = None

    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {}

    @classmethod
    def get_description(cls) -> str:
        return "Get last job records status"

    async def handle(self) -> Response:
        self._task = asyncio.get_event_loop().create_task(self._create_drop_down_menu())
        return self.get_response("Loading jobs drop down menu..")

    async def _validate_drop_down_configurations(self) -> ChannelConfig | None:
        if (config := self._bot.get_configuration(self._channel_id)) is None:
            config = await self._bot.get_channel_configuration(self._channel_id, self._channel_name)
            if config is None:
                return None

        if not config.prow_configurations:
            await self._bot.add_ephemeral_comment(
                self._channel_id,
                self.user_id,
                "Cannot preform this action, `prow_configurations` key is missing on "
                "the configuration file. Please update the configuration file and try"
                " again.\n```$ cat bug_master_configuration.yaml```\n"
                "```prow_configurations:\n  owner: repo-owner\n  repo: repo-name\n  "
                "files:\n    - path/to/jobs/periodics/configuration/file.yaml"
                "\n  ...\n```",
            )

            logger.info(f"Missing job-info configurations for channel {self._channel_name}:{self._channel_id}")
            return None

        return config

    async def _create_drop_down_menu(self):
        if not (config := (await self._validate_drop_down_configurations())):
            logger.warning("Invalid configuration while trying to run jobinfo command")
            return

        drop_down = JobsDropDown(self._bot)
        attachments = await drop_down.get_drop_down(channel_config=config, next_id=DaysRangeDropDown.callback_id())
        drop_down_comment = await self._bot.add_comment(
            self._user_id, "Select job from the drop down menu", attachments=attachments
        )
        user_bot_conversations = await self._bot.users_conversations(user=self._user_id, types="im")

        permlink = "on the user-bot conversation under `Apps` section (below `Direct Messages`."
        for c in user_bot_conversations.data.get("channels", []):
            if (c_id := c.get("id")) and c_id.startswith("D"):
                permlink = f"<{self._bot.org_url}archives/{c_id} | here>"
                break

        message = "| " + drop_down_comment.data.get("message", {}).get("text", "") + "\n" + "=" * 10 + "\n"
        ephemeral_comment = await self._bot.add_ephemeral_comment(
            self._channel_id, self._user_id, message + f"Drop down menu can be found {permlink}"
        )
        if ephemeral_comment.status_code != 200:
            logger.error(f"Failed to post ephemeral_comment, {ephemeral_comment}")
