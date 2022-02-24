import json
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup, element

from . import consts
from .channel_config_handler import ChannelFileConfig
from .consts import logger
from .entities import Comment, CommentType


@dataclass
class ProwResource:
    full_name: str
    build_id: str
    org: str
    repo: str
    branch: str
    variant: str = ""
    __name: str = ""

    @classmethod
    def get_prow_resource(cls, resource: dict) -> "ProwResource":
        labels = resource.get("metadata", {}).get("labels", {})
        spec = resource.get("spec", {})
        full_name = spec.get("job")
        organization = labels.get("prow.k8s.io/refs.org", "")
        branch = labels.get("prow.k8s.io/refs.base_ref", "")
        repo = labels.get("prow.k8s.io/refs.repo", "")
        build_id = labels.get("prow.k8s.io/build-id", "")
        variant = ""

        container_args = spec.get("pod_spec", {}).get("containers", [{}])[0].get("args", [])
        for k, v in [a.replace("--", "").split("=") for a in container_args]:
            if k == "variant":
                variant = v
                break

        return ProwResource(full_name, build_id, organization, repo, branch, variant)

    @property
    def name(self):
        if self.__name:
            return self.__name

        prefix = f"periodic-ci-{self.org}-{self.repo}-{self.branch}-{self.variant + '-' if self.variant else ''}"
        self.__name = self.full_name.replace(prefix, "")
        return self.__name


class ProwJobFailure:
    BASE_STORAGE_URL = "https://storage.googleapis.com/origin-ci-test/logs/"
    MAIN_PAGE_URL = "https://prow.ci.openshift.org/view/gs/origin-ci-test/logs"
    DIRS_STORAGE_URL = "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/origin-ci-test/logs/"
    MIN_FILE_SIZE = 4

    def __init__(self, failure_link: str) -> None:
        """Initialization in this object is asynchronous - tot create new ProwResource call:
        prow_resources = await ProwResource(link).load()
        """
        self._raw_link = failure_link
        self._storage_link = ""
        self._resource: Optional[ProwResource] = None

    @property
    def url(self):
        return self._raw_link

    @property
    def job_name(self):
        return self._resource.name

    @property
    def build_id(self):
        return self._resource.build_id

    async def get_content(self, file_path: str, storage_link=None) -> Union[str, None]:
        if storage_link is None:
            storage_link = self._storage_link

        storage_link = storage_link + "/" if not storage_link.endswith("/") else storage_link
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

    async def _update_actions(self, file_path: str, contains: str, config_entry: dict) -> Tuple[Set[str], Set[Comment]]:
        comments, reactions, raw_comments = set(), set(), set()
        reaction = comment = None
        is_applied = False

        if ("job_name" in config_entry and (
                self.job_name.startswith(config_entry.get("job_name")) or
                self._resource.full_name.startswith(config_entry.get("job_name"))
        )):
            reaction, comment = config_entry.get("emoji"), config_entry.get("text")
            is_applied = True

        elif file_path.endswith("*"):
            reaction, comment = await self.glob(file_path, config_entry)
            if reaction or comment:
                is_applied = True
        else:
            content = await self.get_content(file_path)
            if contains and contains in content:
                reaction, comment = config_entry.get("emoji"), config_entry.get("text")
                is_applied = True

        reactions.add(reaction) if reaction else None
        raw_comments.add(comment) if comment else None

        for comment in raw_comments:
            comments.add(Comment(text=comment, type=CommentType.ERROR_INFO, parse="full"))

        if is_applied and "assignees" in config_entry:
            for action in self._apply_assignee_actions(config_entry):
                comments.add(action)

        return reactions, comments

    @classmethod
    def _apply_assignee_actions(cls, config_entry: dict) -> List[Comment]:
        link_comment = None
        if "assignees" not in config_entry:
            return []

        assignee = config_entry.get("assignees")
        disable_auto_assign = assignee.get("disable_auto_assign", consts.DISABLE_AUTO_ASSIGN_DEFAULT)
        issue_url = assignee.get("issue_url", None)
        users = " ".join([f"@{username}" for username in assignee["users"]])

        if disable_auto_assign:
            return []

        comment = Comment(
            text=f"{users} You have been automatically assigned to investigate this job failure",
            parse="full",
            type=CommentType.ASSIGNEE,
        )
        if issue_url:
            link_comment = Comment(text=f"See <{issue_url}|link> for more information", type=CommentType.MORE_INFO)

        return [comment, link_comment] if link_comment else [comment]

    async def get_failure_actions(
        self, channel: str, channel_config: ChannelFileConfig
    ) -> Tuple[List[str], List[Comment]]:
        comments, reactions = await self._get_job_actions(channel_config)

        if channel_config.disable_auto_assign:
            logger.info(
                f"Skipping automatic assign for {channel} due to that `disable_auto_assign` flag was set to True"
            )
            return list(reactions), list(comments)

        self._append_assignees_comments(channel_config, comments)

        return list(reactions), list(comments)

    @classmethod
    def _join_comments(cls, comments: Set[Comment]) -> Comment:
        comment_text = "\n".join([comment.text for comment in sorted(comments, key=lambda c: c.type.value)])
        return Comment(text=comment_text, type=CommentType.ERROR_INFO, parse="all")

    async def _get_job_actions(self, channel_config: ChannelFileConfig) -> Tuple[Set[Comment], Set[str]]:
        reactions = set()
        comments = set()

        for action in channel_config.actions_items():
            conditions = action.get(
                "conditions", [{"contains": action.get("contains", ""), "file_path": action.get("file_path", "")}]
            )
            for condition in conditions:
                result_reactions, result_comments = await self.format_and_update_actions(
                    **condition, config_entry=action
                )

                for comment in result_comments:
                    comments.add(comment)
                reactions.update(result_reactions)

        return comments, reactions

    def _append_assignees_comments(self, channel_config: ChannelFileConfig, comments: Set[Comment]):
        for assignee in channel_config.assignees_items():
            self._append_assignees_comment(assignee, channel_config, comments)

    def _append_assignees_comment(self, assignee: dict, channel_config: ChannelFileConfig, comments: Set[Comment]):
        if self.job_name.startswith(assignee["job_name"]):
            username = " ".join([f"@{username}" for username in assignee["users"]])

            link_comment = ""
            comment = Comment(
                text=f"{username} You have been automatically assigned to investigate this job failure",
                parse="full",
                type=CommentType.ASSIGNEE,
            )
            if channel_config.assignees_issue_url:
                link_comment = Comment(
                    text=f"See <{channel_config.assignees_issue_url}|link> for more information",
                    type=CommentType.MORE_INFO,
                )

            comments.update([comment, link_comment]) if link_comment else comments.update([comment])

    async def format_and_update_actions(
        self, file_path: str, contains: str, config_entry: dict
    ) -> Tuple[Set[str], Set[Comment]]:
        if "{job_name}" in file_path:
            file_path = file_path.format(job_name=self.build_id)

        return await self._update_actions(file_path, contains, config_entry)

    async def load(self):
        url = self._raw_link.replace(self.MAIN_PAGE_URL, self.BASE_STORAGE_URL)
        job_raw_resource = await self.get_content("prowjob.json", url)
        if not job_raw_resource:
            return None

        resource = ProwResource.get_prow_resource(json.loads(job_raw_resource))
        self._storage_link = urljoin(urljoin(self.BASE_STORAGE_URL, resource.full_name + "/"), f"{resource.build_id}/")
        self._resource = resource
        return self
