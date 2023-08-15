import json
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup, element
from cache import AsyncTTL

from bug_master import consts
from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.consts import logger
from bug_master.entities import Action, Comment, CommentType, Reaction
from bug_master.utils import Utils


@dataclass
class ProwResource:
    full_name: str
    build_id: str
    org: str
    repo: str
    branch: str
    variant: str = ""
    name: str = ""

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

        container_args = (
            spec.get("pod_spec", {}).get("containers", [{}])[0].get("args", [])
        )
        for k, v in [a.replace("--", "").split("=") for a in container_args]:
            if k == "variant":
                variant = v
                break

        return ProwResource(full_name, build_id, organization, repo, branch, variant)

    @property
    def name(self):
        if self.name:
            return self.name

        prefix = f"periodic-ci-{self.org}-{self.repo}-{self.branch}-{self.variant + '-' if self.variant else ''}"
        self.name = self.full_name.replace(prefix, "")
        return self.name


class ProwJobFailure:
    BASE_STORAGE_URL = "https://storage.googleapis.com/origin-ci-test/logs/"
    MAIN_PAGE_URL = "https://prow.ci.openshift.org/view/gs/origin-ci-test/logs"
    DIRS_STORAGE_URL = (
        "https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/origin-ci-test/logs/"
    )
    MIN_FILE_SIZE = 4

    def __init__(self, failure_link: str, message_ts: str) -> None:
        """Initialization in this object is asynchronous - tot create new ProwResource call:
        prow_resources = await ProwResource(link).load()
        """
        self._raw_link = failure_link
        self._storage_link = ""
        self._message_ts = message_ts
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

    # @AsyncTTL(time_to_live=86400, maxsize=1024, skip_args=1)
    async def get_content(self, file_path: str, storage_link: str) -> Union[str, None]:
        if not file_path:
            return None

        logger.debug(
            f"Get file content from {file_path} with base storage link {storage_link}"
        )
        storage_link = (
            storage_link + "/" if not storage_link.endswith("/") else storage_link
        )
        full_file_url = urljoin(storage_link, file_path)
        logger.info(f"Opening a session to {full_file_url} ...")
        if (content := await Utils.get_file_content(full_file_url)) is not None:
            return content

        return None

    @AsyncTTL(time_to_live=86400, maxsize=1024, skip_args=1)
    async def glob(
        self, dir_path: str, result: dict
    ) -> Tuple[Optional[str], Optional[str]]:
        if dir_path.endswith("*"):
            dir_path = dir_path[:-1]
        dir_content = await self.get_content(
            dir_path,
            self._storage_link.replace(self.BASE_STORAGE_URL, self.DIRS_STORAGE_URL),
        )

        if not dir_content:
            logger.error(
                f"Empty dir {dir_path} content. Please check directory path or if prow is up."
            )
            return None, None

        navigable_strings = [
            [c for c in tag.contents if isinstance(c, element.NavigableString)]
            for tag in BeautifulSoup(dir_content, "html.parser").find_all("a")
            if hasattr(tag, "contents")
        ]
        files = [
            str(f.pop()).strip()
            for f in navigable_strings
            if len(f) > 0 and len(f[0]) > self.MIN_FILE_SIZE
        ]

        for file in files:
            file_path = urljoin(dir_path, file)
            content = await self.get_content(file_path, self._storage_link)
            contains = result.get("contains")
            if contains and content and contains in content:
                return result.get("emoji"), result.get("text")
        return None, None

    async def _update_actions(
        self, file_path: str, contains: str, config_entry: dict, ignore_others: bool
    ) -> List[Action]:
        reaction = comment = None
        is_applied = False
        actions = list()

        description = config_entry.get("description", "")
        action_id = config_entry.get("action_id", None)

        if "job_name" in config_entry and (
            self.job_name.startswith(config_entry.get("job_name"))
            or self._resource.full_name.startswith(config_entry.get("job_name"))
        ):
            reaction, comment = config_entry.get("emoji"), config_entry.get("text")
            is_applied = True

        elif file_path.endswith("*"):
            reaction, comment = await self.glob(file_path, config_entry)
            if reaction or comment:
                is_applied = True
        else:
            content = await self.get_content(file_path, self._storage_link)
            if content is None:
                return actions

            if contains and contains in content:
                reaction, comment = config_entry.get("emoji"), config_entry.get("text")
                is_applied = True

        if reaction or comment:
            action = Action(
                action_id, description, self._message_ts, ignore_others=ignore_others
            )
            action.reaction = Reaction(emoji=reaction) if reaction else None
            action.comment = (
                Comment(text=comment, type=CommentType.ERROR_INFO, parse="full")
                if comment
                else None
            )
            actions.append(action)

        if is_applied and "assignees" in config_entry:
            actions += self._apply_assignee_actions(
                config_entry, action_id, description
            )  # assignee inside action

        return actions

    def _apply_assignee_actions(
        self, config_entry: dict, action_id: str, description: str
    ) -> List[Action]:
        link_comment = None
        if "assignees" not in config_entry:
            return []

        assignee = config_entry.get("assignees")
        disable_auto_assign = assignee.get(
            "disable_auto_assign", consts.DISABLE_AUTO_ASSIGN_DEFAULT
        )
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
            link_comment = Comment(
                text=f"See <{issue_url}|link> for more information",
                type=CommentType.MORE_INFO,
            )

        action = Action(action_id, description, self._message_ts, comment=comment)
        return (
            [
                action,
                Action(action_id, description, self._message_ts, comment=link_comment),
            ]
            if link_comment
            else [action]
        )

    async def get_failure_actions(
        self, channel: str, channel_config: ChannelFileConfig, filter_id: str = None
    ) -> List[Action]:
        actions = await self._get_job_actions(channel_config, filter_id)

        if channel_config.disable_auto_assign:
            logger.info(
                f"Skipping automatic assign for {channel} due to that `disable_auto_assign` flag was set to True"
            )
            return actions

        for assignees in channel_config.assignees_items():
            self._apply_global_assignees_actions(assignees, actions)

        return actions

    def _apply_global_assignees_actions(self, assignees: dict, actions: List[Action]):
        jobs = assignees.get("jobs", [assignees.get("job_name")])
        for job in jobs:
            if assignees.get("startswith"):
                assign = self.job_name.startswith(job)
            else:
                assign = self.job_name == job

            if not assign:
                continue

            username = " ".join([f"@{username}" for username in assignees["users"]])
            comment = f"{username} You have been automatically assigned to investigate this job failure"

            action = Action("", "assignees-action", self._message_ts)
            action.comment = Comment(
                text=comment, type=CommentType.ASSIGNEE, parse="full"
            )
            actions.append(action)

    @classmethod
    def _join_comments(cls, comments: Set[Comment]) -> Comment:
        comment_text = "\n".join(
            [comment.text for comment in sorted(comments, key=lambda c: c.type.value)]
        )
        return Comment(text=comment_text, type=CommentType.ERROR_INFO, parse="all")

    async def _get_job_actions(
        self, channel_config: ChannelFileConfig, filter_id: str = None
    ) -> List[Action]:
        """
        :param channel_config:
        :param filter_id: Action filter id as defined in the configuration file
        :return:
        """
        actions = list()

        for action_data in channel_config.actions_items():
            try:
                if filter_id and (
                    action_data.get("action_id") is None
                    or action_data.get("action_id") != filter_id
                ):
                    continue

                ignore_others = action_data.get("ignore_others", None)

                conditions = action_data.get(
                    "conditions",
                    [
                        {
                            "contains": action_data.get("contains", ""),
                            "file_path": action_data.get("file_path", ""),
                        }
                    ],
                )

                for condition in conditions:
                    actions += await self.format_and_update_actions(
                        **condition,
                        config_entry=action_data,
                        ignore_others=ignore_others,
                    )
            except UnicodeDecodeError as e:
                logger.error(f"{e}, Action data: {action_data}")

        return actions

    async def format_and_update_actions(
        self, file_path: str, contains: str, config_entry: dict, ignore_others: bool
    ) -> List[Action]:
        if not file_path or not contains:
            return []

        if "{job_name}" in file_path:
            file_path = file_path.format(job_name=self.job_name)

        return await self._update_actions(
            file_path, contains, config_entry, ignore_others
        )

    async def load(self):
        url = self._raw_link.replace(self.MAIN_PAGE_URL, self.BASE_STORAGE_URL)
        job_raw_resource = await self.get_content("prowjob.json", url)
        if not job_raw_resource:
            return None

        resource = ProwResource.get_prow_resource(json.loads(job_raw_resource))
        self._storage_link = urljoin(
            urljoin(self.BASE_STORAGE_URL, resource.full_name + "/"),
            f"{resource.build_id}/",
        )
        self._resource = resource
        return self
