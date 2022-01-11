import re
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import aiohttp

from bug_master.bug_master_bot import BugMasterConfig


class ProwJobFailure:
    BASE_STORAGE_URL = "https://storage.googleapis.com/origin-ci-test/logs/"
    DIRS_STORAGE_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/origin-ci-test/logs/"
    JOB_PREFIX = "periodic-ci-openshift-assisted-test-infra-master-"

    def __init__(self, failure_link: str, config: BugMasterConfig) -> None:
        self._raw_link = failure_link
        self._job_full_name, self._job_name, self.job_id = self._get_job_data(failure_link)
        self._storage_link = urljoin(urljoin(self.BASE_STORAGE_URL, self._job_full_name), f"{self.job_id}/")
        self._config = config

    @property
    def url(self):
        return self._raw_link

    @property
    def name(self):
        return self._job_full_name

    def _get_job_data(self, link: str):
        job_full_name, job_id = re.findall(r"logs/(.*?)/(\d{15,22})", link).pop()
        job_full_name = job_full_name if job_full_name.endswith("/") else job_full_name + "/"
        job_name = re.findall(r"(e2e-.*?)[\s|/]", job_full_name).pop()
        return job_full_name, job_name, job_id

    async def get_content(self, file_path: str, storage_link=None):
        if storage_link is None:
            storage_link = self._storage_link
        async with aiohttp.ClientSession() as session:
            async with session.get(urljoin(storage_link, file_path)) as resp:
                if resp.status == 200:
                    return await resp.text()

        return None

    async def glob(self, dir_path: str, result: dict) -> Tuple[Optional[str], Optional[str]]:
        if dir_path.endswith("*"):
            dir_path = dir_path[:-1]
        dir_content = await self.get_content(
            dir_path, self._storage_link.replace(self.BASE_STORAGE_URL, self.DIRS_STORAGE_URL)
        )
        for file in re.findall(r"> (junit_.*?)</a>", dir_content):
            file_path = urljoin(dir_path, file)
            content = await self.get_content(file_path)
            contains = result.get("contains")
            if contains and contains in content:
                return result.get("emoji"), result.get("text")
        return None, None

    async def get_failure_result(self) -> Tuple[List[str], List[str]]:
        emojis = []
        texts = []
        for result in self._config:
            file_path = result.get("file_path", "")
            if "{job_name}" in file_path:
                file_path = file_path.format(job_name=self._job_name)
            if file_path.endswith("*"):
                emoji, text = await self.glob(file_path, result)
                if emoji:
                    emojis.append(emoji)
                if text:
                    texts.append(text)
                continue
            content = await self.get_content(file_path)
            contains = result.get("contains")
            if contains and contains in content:
                emoji, text = result.get("emoji"), result.get("text")
                if emoji:
                    emojis.append(emoji)
                if text:
                    texts.append(text)
                continue
        return emojis, texts
