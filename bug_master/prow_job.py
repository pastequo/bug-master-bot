import re
from typing import List, Optional, Set, Tuple
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, element

from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.entities import Comment, CommentType


class ProwJobFailure:
    BASE_STORAGE_URL = "https://storage.googleapis.com/origin-ci-test/logs/"
    DIRS_STORAGE_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/origin-ci-test/logs/"
    JOB_PREFIX = "periodic-ci-openshift-assisted-test-infra-master-"
    MIN_FILE_SIZE = 4

    def __init__(self, failure_link: str) -> None:
        self._raw_link = failure_link
        self._job_full_name, self._job_name, self.job_id = self._get_job_data(failure_link)
        self._storage_link = urljoin(urljoin(self.BASE_STORAGE_URL, self._job_full_name), f"{self.job_id}/")

    @property
    def url(self):
        return self._raw_link

    @property
    def name(self):
        return self._job_name

    @classmethod
    def _get_job_data(cls, link: str):
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

        navigable_strings = [
            [c for c in tag.contents if isinstance(c, element.NavigableString)]
            for tag in BeautifulSoup(dir_content, "html.parser").find_all("a")
            if hasattr(tag, "contents")
        ]
        files = [str(f.pop()).strip() for f in navigable_strings if len(f) > 0 and len(f[0]) > self.MIN_FILE_SIZE]

        for file in files:
            file_path = urljoin(dir_path, file)
            content = await self.get_content(file_path)
            contains = result.get("contains")
            if contains and content and contains in content:
                return result.get("emoji"), result.get("text")
        return None, None

    async def _update_actions(self, file_path: str, contains: str, config_entry: dict) -> Tuple[Set[str], Set[str]]:
        reactions, comments = set(), set()
        reaction = comment = None

        if "job_name" in config_entry and self._job_name.startswith(config_entry.get("job_name")):
            reaction, comment = config_entry.get("emoji"), config_entry.get("text")

        elif file_path.endswith("*"):
            reaction, comment = await self.glob(file_path, config_entry)
        else:
            content = await self.get_content(file_path)
            if contains and contains in content:
                reaction, comment = config_entry.get("emoji"), config_entry.get("text")

        reactions.add(reaction) if reaction else None
        comments.add(comment) if comment else None

        return reactions, comments

    async def get_failure_actions(self, bot_config: ChannelFileConfig) -> Tuple[List[str], List[Comment]]:
        reactions = set()
        comments = set()
        for action in bot_config.actions_items():
            conditions = action.get(
                "conditions", [{"contains": action.get("contains", ""), "file_path": action.get("file_path", "")}]
            )
            for condition in conditions:
                result_reactions, result_comments = await self.format_and_update_actions(
                    **condition, config_entry=action
                )
                for comment in result_comments:
                    comments.add(Comment(text=comment, type=CommentType.ERROR_INFO))
                reactions.update(result_reactions)

        for assignees in bot_config.assignees_items():
            if self._job_name.startswith(assignees["job_name"]):
                username = " ".join([f"@{username}" for username in assignees["users"]])

                link_comment = ""
                comment = Comment(
                    text=f"{username} You have been automatically assigned to investigate this job failure",
                    parse="full",
                    type=CommentType.ASSIGNEE,
                )
                if bot_config.assignees_issue_url:
                    link_comment = Comment(
                        text=f"See <{bot_config.assignees_issue_url}|link> for more information",
                        type=CommentType.MORE_INFO,
                    )

                comments.update([comment, link_comment]) if link_comment else comments.update([comment])
                break

        return list(reactions), list(comments)

    async def format_and_update_actions(
        self, file_path: str, contains: str, config_entry: dict
    ) -> Tuple[Set[str], Set[str]]:
        if "{job_name}" in file_path:
            file_path = file_path.format(job_name=self._job_name)

        return await self._update_actions(file_path, contains, config_entry)
