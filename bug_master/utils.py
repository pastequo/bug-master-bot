import base64
import json
from abc import ABC
from dataclasses import dataclass
from datetime import datetime
from typing import List, Union

import aiohttp
import yaml
from bs4 import BeautifulSoup
from cache import AsyncTTL
from dateutil import parser

from .consts import logger


@dataclass
class JobStatus:
    job_id: str
    started: datetime
    succeeded: bool


class Utils(ABC):
    GIT_API_FMT = "https://api.github.com/repos/{ORG}/{REPO}/contents/{PATH}"
    SPYGLASS_JOB_HISTORY_URL_FMT = "https://prow.ci.openshift.org/job-history/gs/origin-ci-test/logs/{JOB_NAME}"

    @classmethod
    async def get_file_content(cls, url: str, headers: dict = None) -> str | None:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                if not resp.status == 200:
                    logger.error(
                        f"Failed to load file data file is missing of invalid URL {url} with headers {headers}"
                        f". Returned status {resp.status}"
                    )
                    return None

                return await resp.text()

    @classmethod
    async def get_yaml_file_content(cls, url: str, headers: dict = None) -> dict:
        content = await cls.get_file_content(url, headers)
        return yaml.safe_load(content) if content else {}

    @classmethod
    async def get_json_file_content(cls, url: str, headers: dict = None) -> dict:
        content = await cls.get_file_content(url, headers)
        return json.loads(content) if content else {}

    @classmethod
    async def get_git_content(cls, repo: str, owner: str, path: str) -> Union[dict, str]:
        url = cls.GIT_API_FMT.format(ORG=owner, REPO=repo, PATH=path)
        data = await cls.get_json_file_content(url)

        content = base64.b64decode(data.get("content"))
        if data.get("name").endswith(".yaml"):
            return yaml.safe_load(content)
        if data.get("name").endswith(".json"):
            return json.loads(content)

        return content.decode()

    @classmethod
    @AsyncTTL(time_to_live=360, maxsize=None)
    async def get_jobs_history(cls, job_name: str) -> List[JobStatus]:
        url = cls.SPYGLASS_JOB_HISTORY_URL_FMT.format(JOB_NAME=job_name)
        text = await cls.get_file_content(url)
        script = None

        for script in BeautifulSoup(text, "html.parser").find_all("script"):
            if "SpyglassLink" in script.contents:
                break

        if script:
            jobs = json.loads(str(script.contents[0]).replace("\n", "").split(" = ")[-1][:-1])
            return [JobStatus(j.get("ID"), parser.parse(j.get("Started")), j.get("Result") == "SUCCESS") for j in jobs]

        return []

    @classmethod
    async def get_channel_config(cls, bot, channel_id: str, channel_name: str = ""):
        if (config := bot.get_configuration(channel_id)) is None:
            config = await bot.get_channel_configuration(channel_id, channel_name)

        return config
