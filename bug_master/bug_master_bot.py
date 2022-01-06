import asyncio
import json
from asyncio import AbstractEventLoop
from typing import Dict, Union

import aiohttp
import yaml
from slack_sdk import signature
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from .consts import logger


class BugMasterConfig:
    SUPPORTED_FILETYPE = ("yaml", "json")

    def __init__(self, file_info: dict) -> None:
        if not file_info:
            raise ValueError(f"Invalid file info {file_info}")

        filetype = file_info["filetype"]
        if filetype not in self.SUPPORTED_FILETYPE:
            raise TypeError(f"Invalid file type. Got {filetype} expected to be one of {self.SUPPORTED_FILETYPE}")

        self._title = file_info["title"]
        self._filetype = filetype
        self._url = file_info["url_private"]
        self._content = None

    def __iter__(self):
        return self._content.__iter__()

    @property
    def name(self):
        return self._title

    async def load(self, bot_token: str) -> "BugMasterConfig":
        content = {}
        headers = {"Authorization": "Bearer %s" % bot_token}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self._url) as resp:
                if resp.status == 200:
                    raw_content = await resp.text()
                else:
                    self._content = {}
                    return self

            if self._filetype == "yaml":
                content = yaml.safe_load(raw_content)
            elif self._filetype == "json":
                content = json.loads(raw_content)
            else:
                logger.warning("Invalid configuration file found")

            self._content = content
            self.validate_configurations(content)
            return self

    @classmethod
    def validate_configurations(cls, content):
        assert isinstance(content, list)
        assert isinstance(content[0], dict) if len(content) > 0 else True


class BugMasterBot:
    def __init__(self, bot_token: str, app_token: str, signing_secret: str, loop: AbstractEventLoop = None) -> None:
        self._sm_client = SocketModeClient(app_token=app_token, web_client=AsyncWebClient(bot_token))
        self._verifier = signature.SignatureVerifier(signing_secret)
        self._loop = loop or asyncio.get_event_loop()
        self._bot_token = bot_token
        self._config: Dict[str, BugMasterConfig] = {}
        self._id = None
        self._name = None

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._name

    def has_channel_configurations(self, channel: str):
        return channel in self._config

    async def add_reaction(self, channel: str, emoji: str, ts: str) -> AsyncSlackResponse:
        return await self._sm_client.web_client.reactions_add(channel=channel, name=emoji, timestamp=ts)

    async def add_comment(self, channel: str, comment: str, ts: str = None) -> AsyncSlackResponse:
        return await self._sm_client.web_client.chat_postMessage(channel=channel, text=comment, thread_ts=ts)

    def get_configuration(self, channel: str) -> Union[BugMasterConfig, None]:
        return self._config.get(channel, None)

    def _get_configuration(self, channel: str, files: list = None):
        if channel not in self._config:
            return BugMasterConfig(files.pop() if files else [])
        return self._config[channel]

    async def refresh_configuration(self, channel: str, files: str, from_history=False) -> bool:
        res = False
        files = [
            f
            for f in sorted(files, key=lambda f: f["timestamp"])
            if f["title"].startswith("bug_master_configuration.yaml")
        ]
        if not files:
            return res

        bmc = self._get_configuration(channel, files)

        try:
            await bmc.load(self._bot_token)
            self._config[channel] = bmc
            res = True
        except AssertionError:
            if not from_history:
                await self.add_comment(channel, "BugMasterBot configuration file is invalid")
            return False

        if not from_history:
            await self.add_comment(
                channel, f"BugMasterBot configuration file `{self._config[channel].name}` " f"updated successfully"
            )
        return res

    def start(self) -> "BugMasterBot":
        logger.info("Stating bug_master bot")
        self._loop.run_until_complete(self._sm_client.connect())
        self._update_bot_info()
        return self

    def _update_bot_info(self):
        info = self._loop.run_until_complete(self._sm_client.web_client.auth_test()).data
        if info.get("ok", False):
            self._id = info.get("bot_id")
            self._name = info.get("user")

    async def try_load_configurations_from_history(self, channel: str) -> bool:
        res = await self._sm_client.web_client.files_list(channel=channel, types=BugMasterConfig.SUPPORTED_FILETYPE)
        return await self.refresh_configuration(channel, res.data.get("files", []), from_history=True)

    async def get_channel_info(self, channel: str):
        res = await self._sm_client.web_client.conversations_info(channel=channel)
        return res.get("channel", {})
