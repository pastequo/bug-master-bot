import asyncio
from asyncio import AbstractEventLoop
from typing import Dict, List, Tuple, Union

import slack_sdk
from schema import SchemaError
from slack_sdk import signature
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse
from yaml.scanner import ScannerError

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
        self._bot_id = None
        self._user_id = None
        self._name = None

    def __str__(self):
        return f"{self._name}:{self._bot_id} {self._user_id}"

    @property
    def _web_client(self):
        return self._sm_client.web_client

    @property
    def bot_id(self):
        return self._bot_id

    @property
    def user_id(self):
        return self._user_id

    @property
    def name(self):
        return self._name

    def has_channel_configurations(self, channel_id: str):
        return channel_id in self._config

    async def add_reaction(self, channel: str, emoji: str, ts: str) -> AsyncSlackResponse:
        try:
            return await self._web_client.reactions_add(channel=channel, name=emoji, timestamp=ts)
        except slack_sdk.errors.SlackApiError as e:
            if e.response.data.get("error") == "invalid_name":
                logger.warning(f"Invalid configuration on channel {channel}. {e}, reaction={emoji}")
                return await self.add_comment(
                    channel, f"Invalid reaction `:{emoji}:`." " Please check your configuration file", ts
                )
            raise

    async def add_comment(self, channel: str, comment: str, ts: str = None, parse: str = "none") -> AsyncSlackResponse:
        return await self._web_client.chat_postMessage(channel=channel, text=comment, thread_ts=ts, parse=parse)

    def get_configuration(self, channel: str) -> Union[ChannelFileConfig, None]:
        return self._config.get(channel, None)

    def reset_configuration(self, channel: str):
        del self._config[channel]

    def _get_file_configuration(
            self, channel: str, files: list = None, force_create: bool = False
    ) -> ChannelFileConfig:
        if force_create or channel not in self._config:
            return ChannelFileConfig(files[0] if files else [])
        return self._config[channel]

    async def refresh_file_configuration(
            self, channel: str, files: List[dict], from_history=False, force_create=False, user_id: str = None
    ) -> bool:
        res = False
        sorted_files = [
            f
            for f in sorted(files, key=lambda f: f["timestamp"], reverse=True)
            if f["title"].startswith(consts.CONFIGURATION_FILE_NAME)
        ]
        if not sorted_files:
            return res
        logger.info("Attempting to refresh configuration file")
        bmc = self._get_file_configuration(channel, sorted_files, force_create)
        self._config[channel] = bmc

        try:
            await bmc.load(self._bot_token)
            res = True
            logger.info(f"Configuration file loaded successfully with {len(self._config[channel])} entries")
        except (SchemaError, ScannerError) as e:
            # if not from_history:
            self._config[channel] = bmc
            await self.add_comment(channel, "BugMasterBot configuration file is invalid")
            if user_id:
                await self.add_comment(user_id, f"BugMasterBot configuration file is invalid. "
                                                f"Full error ({e.__class__.__name__}) message: "
                                                f"```{str(e).replace('`', '')}```")

            return False

        if not from_history:
            await self.add_comment(
                channel,
                f"BugMasterBot configuration <{bmc.permalink} | file> `{self._config[channel].name}` "
                f"updated successfully",
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
        info = self._loop.run_until_complete(self._web_client.auth_test()).data
        if info.get("ok", False):
            self._bot_id = info.get("bot_id")
            self._user_id = info.get("user_id")
            self._name = info.get("user")
            logger.info(f"Bot authentication complete - {self}")
        else:
            logger.warning("Can't auth bot web_client")

    async def try_load_configurations_from_history(self, channel: str) -> bool:
        res = await self._web_client.files_list(channel=channel, types=ChannelFileConfig.SUPPORTED_FILETYPE)
        is_conf_valid = await self.refresh_file_configuration(channel, res.data.get("files", []), from_history=True)
        if is_conf_valid:
            logger.info(f"Configurations loaded successfully from channel history for channel {channel}")
        return is_conf_valid

    async def get_file_info(self, file_id: str) -> dict:
        res = await self._web_client.files_info(file=file_id)
        return res.data.get("file")

    async def get_channel_info(self, channel_id: str) -> dict:
        res = await self._web_client.conversations_info(channel=channel_id)
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

    async def get_messages(self, channel_id: str, messages_count: int, cursor: str = None) -> Tuple[List[dict], str]:
        res = await self._web_client.conversations_history(channel=channel_id, limit=messages_count, cursor=cursor)
        return res.data.get("messages", []), res.data.get("response_metadata", {}).get("next_cursor")
