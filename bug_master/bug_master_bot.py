import asyncio
from asyncio import AbstractEventLoop
from typing import Dict, List, Union

import slack_sdk
from schema import SchemaError
from slack_sdk import signature
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from . import consts
from .channel_config_handler import ChannelFileConfig
from .consts import logger
from .models import Channel


class BugMasterBot:
    def __init__(self, bot_token: str, app_token: str, signing_secret: str, loop: AbstractEventLoop = None) -> None:
        self._sm_client = SocketModeClient(app_token=app_token, web_client=AsyncWebClient(bot_token))
        self._verifier = signature.SignatureVerifier(signing_secret)
        self._loop = loop or asyncio.get_event_loop()
        self._bot_token = bot_token
        self._config: Dict[str, ChannelFileConfig] = {}
        self._id = None
        self._name = None

    def __str__(self):
        return f"{self._name}:{self._id}"

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    def has_channel_configurations(self, channel: str):
        return channel in self._config

    async def add_reaction(self, channel: str, emoji: str, ts: str) -> AsyncSlackResponse:
        try:
            return await self._sm_client.web_client.reactions_add(channel=channel, name=emoji, timestamp=ts)
        except slack_sdk.errors.SlackApiError as e:
            if e.response.data.get("error") == "invalid_name":
                logger.warning(f"Invalid configuration on channel {channel}. {e}, reaction={emoji}")
                return await self.add_comment(
                    channel, f"Invalid reaction `:{emoji}:`." " Please check your configuration file", ts
                )
            raise

    async def add_comment(self, channel: str, comment: str, ts: str = None) -> AsyncSlackResponse:
        return await self._sm_client.web_client.chat_postMessage(channel=channel, text=comment, thread_ts=ts)

    def get_configuration(self, channel: str) -> Union[ChannelFileConfig, None]:
        return self._config.get(channel, None)

    def _get_file_configuration(self, channel: str, files: list = None) -> ChannelFileConfig:
        if channel not in self._config:
            return ChannelFileConfig(files[0] if files else [])
        return self._config[channel]

    async def refresh_file_configuration(self, channel: str, files: List[dict], from_history=False) -> bool:
        res = False
        files = [
            f
            for f in sorted(files, key=lambda f: f["timestamp"])
            if f["title"].startswith(consts.CONFIGURATION_FILE_NAME)
        ]
        if not files:
            return res
        logger.info("Attempting to refresh configuration file")
        bmc = self._get_file_configuration(channel, files)
        self._config[channel] = bmc

        try:
            await bmc.load(self._bot_token)
            res = True
            logger.info(f"Configuration file loaded successfully with {len(self._config[channel])} entries")
        except SchemaError:
            # if not from_history:
            self._config[channel] = bmc
            await self.add_comment(channel, "BugMasterBot configuration file is invalid")
            return False

        if not from_history:
            await self.add_comment(
                channel, f"BugMasterBot configuration file `{self._config[channel].name}` " f"updated successfully"
            )
        return res

    def start(self) -> "BugMasterBot":
        logger.info("Starting bug_master bot - attempting connect to Slack’s APIs using WebSockets ...")
        try:
            self._loop.run_until_complete(self._sm_client.connect())
            logger.info("Connected to bot Slack’s APIs")
        except SlackApiError as e:
            logger.error(f"Connection to Slack’s APIs failed, {e}")
            raise

        self._update_bot_info()
        return self

    def _update_bot_info(self):
        info = self._loop.run_until_complete(self._sm_client.web_client.auth_test()).data
        if info.get("ok", False):
            self._id = info.get("bot_id")
            self._name = info.get("user")
            logger.info(f"Bot authentication complete - {self}")
        else:
            logger.warning("Can't auth bot web_client")

    async def try_load_configurations_from_history(self, channel: str) -> bool:
        res = await self._sm_client.web_client.files_list(channel=channel, types=ChannelFileConfig.SUPPORTED_FILETYPE)
        is_conf_valid = await self.refresh_file_configuration(channel, res.data.get("files", []), from_history=True)
        if is_conf_valid:
            logger.info(f"Configurations loaded successfully from channel history for channel {channel}")
        return is_conf_valid

    async def get_file_info(self, file_id: str) -> dict:
        res = await self._sm_client.web_client.files_info(file=file_id)
        return res.data.get("file")

    async def get_channel_info(self, channel_id: str) -> dict:
        res = await self._sm_client.web_client.conversations_info(channel=channel_id)
        channel_info = res.get("channel", None)

        if not channel_info:
            return {}

        channel = Channel.select(channel_id)
        if not channel:
            Channel.create(
                id=channel_info.get("id"), name=channel_info.get("name"), is_private=channel_info.get("is_private")
            )
        else:
            channel.update_last_seen()

        return channel_info
