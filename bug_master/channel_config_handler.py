import json
from copy import deepcopy
from typing import Any, Dict, List, Union

import aiohttp
import yaml
from loguru import logger
from schema import Optional, Or, Schema, SchemaError

from bug_master import consts
from bug_master.utils import Utils


class BaseChannelConfig:
    _config_schema = Schema(
        {
            Optional("remote_configurations"): {"url": str},
            Optional("prow_configurations"): {"owner": str, "repo": str, "files": [str]},
            Optional("assignees"): {
                Optional("disable_auto_assign"): bool,
                "issue_url": str,
                "data": [{"job_name": str, "users": [str]}],
            },
            Optional("actions"): [
                {
                    "description": str,
                    Or("emoji", "text"): str,
                    Optional("action_id"): str,
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
        self._prow_configurations: List[dict] = []
        self._assignees: dict = {}

    def __key(self):
        return str(self._prow_configurations) + str(self._actions)

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, other):
        if isinstance(other, BaseChannelConfig):
            return self.__key() == other.__key()
        return NotImplemented

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
        self._remote_url = None

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
    def remote_url(self) -> str:
        return self._remote_url

    @property
    def remote_repository(self) -> str:
        if not self._remote_url:
            return ""

        repo = self._remote_url.replace("raw.githubusercontent.com", "github.com")
        return repo.replace("/main/", "/blob/main/")

    @property
    def assignees_issue_url(self):
        if self._assignees:
            return self._assignees.get("issue_url", "")
        return ""

    def actions_items(self):
        return self._actions.__iter__()

    @property
    def prow_configurations(self) -> dict:
        return deepcopy(self._prow_configurations)

    def assignees_items(self):
        return self._assignees.get("data", []).__iter__()

    async def _get_file_content(self, bot_token: str, url: str) -> Union[dict, None]:
        content = {}
        headers = None
        if self._remote_url is None:
            headers = {"Authorization": "Bearer %s" % bot_token}

        if (raw_content := await Utils.get_file_content(url, headers)) is None:
            return {}

        if self._filetype == "yaml":
            content = yaml.safe_load(raw_content)
        elif self._filetype == "json":
            content = json.loads(raw_content)
        else:
            logger.warning("Invalid configuration file found")

        if self._remote_url is None and (remote_configurations := content.get("remote_configurations")) is not None:
            self._remote_url = remote_configurations.get("url")
            logger.info(f"Loading remote configurations {self._remote_url}")
            return await self._get_file_content(bot_token, self._remote_url)

        return content

    async def load(self, bot_token: str) -> "ChannelFileConfig":
        content = await self._get_file_content(bot_token, self._url)

        self.validate_configurations(content)
        self._assignees = content.get("assignees", {})
        self._actions = content.get("actions")
        self._prow_configurations = content.get("prow_configurations")

        return self
