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
        logger.info(f"Getting file content {url}")
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as resp:
                if not resp.status == 200:
                    logger.error(
                        f"Failed to load file data file is missing of invalid URL {url} with headers {headers}"
                        f". Returned status {resp.status}"
                    )
                    return None

                logger.info(f"File content {url} download successfully")
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
        logger.info(f"Loading Git file  content {url}")

        data = await cls.get_json_file_content(url)

        logger.info(f"{url} content loaded")

        content = base64.b64decode(data.get("content"))
        if data.get("name").endswith(".yaml"):
            logger.info(f"Decoding {url} content to yaml dict")
            return yaml.safe_load(content)
        if data.get("name").endswith(".json"):
            logger.info(f"Decoding {url} content to yaml dict")
            return json.loads(content)

        logger.info(f"Can't find any format for {url} content, decoding to string")
        return content.decode()

    @classmethod
    def get_job_history_link(cls, job_name: str):
        return cls.SPYGLASS_JOB_HISTORY_URL_FMT.format(JOB_NAME=job_name)

    @classmethod
    @AsyncTTL(time_to_live=360, maxsize=None)
    async def get_job_history(cls, job_name: str) -> List[JobStatus]:
        url = cls.get_job_history_link(job_name)
        text = await cls.get_file_content(url)
        script = None

        for script in BeautifulSoup(text, "html.parser").find_all("script"):
            if "SpyglassLink" in script.contents:
                break

        if script:
            logger.info(f"Script found for {job_name}, parsing..")
            jobs = json.loads(str(script.contents[0]).replace("\n", "").split(" = ")[-1][:-1])
            return [JobStatus(j.get("ID"), parser.parse(j.get("Started")), j.get("Result") == "SUCCESS") for j in jobs]

        logger.warning(f"Can't find any daya for {job_name}")
        logger.debug(f"File content: {text}")
        return []

    @classmethod
    async def get_channel_config(cls, bot, channel_id: str, channel_name: str = ""):
        if (config := bot.get_configuration(channel_id)) is None:
            config = await bot.get_channel_configuration(channel_id, channel_name)

        return config

    @classmethod
    @AsyncTTL(time_to_live=3600, maxsize=None)
    async def get_jobs(cls, prow_configurations: dict) -> List[str]:
        jobs = []
        repo = prow_configurations.get("repo")
        owner = prow_configurations.get("owner")

        if not prow_configurations:
            logger.warning("Missing job-info configurations")
            return jobs

        for file_path in prow_configurations.get("files", []):
            periodics_jobs_config = await cls.get_git_content(repo=repo, owner=owner, path=file_path)
            _jobs_config = periodics_jobs_config.get("periodics", {})
            periodics_names = [job.get("name") for job in _jobs_config if job.get("name").endswith("periodic")]
            logger.debug(f"Found {len(periodics_names)} jobs on {file_path}")
            jobs += periodics_names

        logger.info(f"Total jobs found {len(jobs)}")
        return jobs
