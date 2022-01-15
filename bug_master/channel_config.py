import json
from typing import Union, List, Dict, Any

import aiohttp
import yaml
from loguru import logger

from schema import Schema, Or, Optional, SchemaError


class ChannelConfig:
    SUPPORTED_FILETYPE = ("yaml", "json")
    _config_schema = Schema([{
        "description": str,
        Or("emoji", "text"): str,
        Optional("contains"): str,
        Optional("file_path"): str,
        Optional("flaky_job_name"): str
    }])

    def __init__(self, file_info: dict) -> None:
        if not file_info:
            raise ValueError(f"Invalid file info {file_info}")

        filetype = file_info["filetype"]
        if filetype not in self.SUPPORTED_FILETYPE:
            raise TypeError(f"Invalid file type. Got {filetype} expected to be one of {self.SUPPORTED_FILETYPE}")

        self._title = file_info["title"]
        self._filetype = filetype
        self._url = file_info["url_private"]
        self._permalink = file_info["permalink"]
        self._content: List[dict] = []

    def __len__(self):
        return len(self._content)

    @property
    def name(self):
        return self._title

    @property
    def permalink(self):
        return self._permalink

    def items(self):
        return self._content.__iter__()

    async def load(self, bot_token: str) -> "ChannelConfig":
        content = {}
        headers = {"Authorization": "Bearer %s" % bot_token}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(self._url) as resp:
                if not resp.status == 200:
                    return self

                raw_content = await resp.text()

            if self._filetype == "yaml":
                content = yaml.safe_load(raw_content)
            elif self._filetype == "json":
                content = json.loads(raw_content)
            else:
                logger.warning("Invalid configuration file found")

            self.validate_configurations(content)
            self._content = content
            return self

    @classmethod
    def validate_configurations(cls, content: List[Dict[str, Any]]):
        try:
            assert isinstance(content, list)
            assert isinstance(content[0], dict) if len(content) > 0 else True
            cls._config_schema.validate(content)
            return True
        except (SchemaError, AssertionError) as e:
            logger.info("Schema validation failed")
            raise SchemaError(f"Failed to validate channel configuration: {content}") from e
