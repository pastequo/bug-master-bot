import json
from typing import Any, Dict, List, Union

import aiohttp
import yaml
from loguru import logger
from schema import Optional, Or, Schema, SchemaError

from bug_master import consts


class BaseChannelConfig:
    _config_schema = Schema(
        {
            Optional("assignees"): {
                Optional("disable_auto_assign"): bool,
                "issue_url": str,
                "data": [{"job_name": str, "users": [str]}],
            },
            "actions": [
                {
                    "description": str,
                    Or("emoji", "text"): str,
                    Optional("contains"): str,
                    Optional("file_path"): str,
                    Optional("job_name"): str,
                    Optional("ignore_others"): bool,
                    Optional("conditions"): [{Optional("contains"): str, Optional("file_path"): str}],
                    Optional("assignees"): {
                        Optional("disable_auto_assign"): bool,
                        Optional("issue_url"): str,
                        "users": [str],
                    },
                }
            ],
        }
    )

    def __init__(self):
        self._actions: List[dict] = []
        self._assignees: dict = {}

    @classmethod
    def get_config_schema(cls) -> Schema:
        return cls._config_schema

    @classmethod
    def validate_configurations(cls, content: Dict[str, Any]):
        try:
            cls._config_schema.validate(content)
            return True
        except (SchemaError, AssertionError) as e:
            logger.info("Schema validation failed")
            raise SchemaError(f"Failed to validate channel configuration: {content}") from e


class ChannelFileConfig(BaseChannelConfig):
    SUPPORTED_FILETYPE = ("yaml", "json")

    def __init__(self, file_info: dict) -> None:
        super().__init__()
        if not file_info:
            raise ValueError(f"Invalid file info {file_info}")

        filetype = file_info["filetype"]
        if filetype not in self.SUPPORTED_FILETYPE:
            raise TypeError(f"Invalid file type. Got {filetype} expected to be one of {self.SUPPORTED_FILETYPE}")

        self._title = file_info["title"]
        self._filetype = filetype
        self._url = file_info["url_private"]
        self._permalink = file_info["permalink"]

    def __len__(self):
        return len(self._actions)

    @property
    def disable_auto_assign(self):
        return (
            self._assignees.get("disable_auto_assign", consts.DISABLE_AUTO_ASSIGN_DEFAULT) if self._assignees else False
        )

    @property
    def name(self):
        return self._title

    @property
    def permalink(self):
        return self._permalink

    @property
    def assignees_issue_url(self):
        if self._assignees:
            return self._assignees.get("issue_url", "")
        return ""

    def actions_items(self):
        return self._actions.__iter__()

    def assignees_items(self):
        return self._assignees.get("data", []).__iter__()

    async def _get_file_content(self, bot_token: str) -> Union[dict, None]:
        content = {}

        async with aiohttp.ClientSession(headers={"Authorization": "Bearer %s" % bot_token}) as session:
            async with session.get(self._url) as resp:
                if not resp.status == 200:
                    return content

                raw_content = await resp.text()

            if self._filetype == "yaml":
                # try:
                content = yaml.safe_load(raw_content)
                # except ScannerError:
                #     # TODO send message to the user
                #     pass
            elif self._filetype == "json":
                content = json.loads(raw_content)
            else:
                logger.warning("Invalid configuration file found")

        return content

    async def load(self, bot_token: str) -> "ChannelFileConfig":
        content = await self._get_file_content(bot_token)

        self.validate_configurations(content)
        self._assignees = content.get("assignees", {})
        self._actions = content.get("actions")
        return self
