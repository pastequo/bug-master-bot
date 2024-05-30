import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Set, Tuple, Union
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from cache import AsyncTTL

from bug_master import consts
from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.consts import logger
from bug_master.entities import Action, Comment, CommentType, Reaction
from bug_master.utils import Utils


@dataclass
class ClusterDirData:
    install_config: str = None
    metadata: str = None
    must_gather: str = None
    cluster_logs: str = None
    cluster_id: str = None
    events: str = None


@dataclass
class ProwResource:
    full_name: str
    build_id: str
    org: str
    repo: str
    branch: str
    variant: str = ""
    job_duration: float = 0.0
    __name: str = ""

    @classmethod
    def get_prow_resource(cls, resource: dict) -> "ProwResource":
        labels = resource.get("metadata", {}).get("labels", {})
        spec = resource.get("spec", {})
        status = resource.get("status", {})
        full_name = spec.get("job")
        organization = labels.get("prow.k8s.io/refs.org", "")
        branch = labels.get("prow.k8s.io/refs.base_ref", "")
        repo = labels.get("prow.k8s.io/refs.repo", "")
        build_id = labels.get("prow.k8s.io/build-id", "")
        variant = ""
        start_time = datetime.fromisoformat(status.get("startTime"))
        completion_time = datetime.fromisoformat(status.get("completionTime"))

        container_args = spec.get("pod_spec", {}).get("containers", [{}])[0].get("args", [])

        for arg in [a.replace("--", "") for a in container_args]:
            splitted_arg = arg.split("=")
            if len(splitted_arg) == 2 and splitted_arg[0] == "variant":
                variant = splitted_arg[1]
                break

        job_duration = (completion_time - start_time).total_seconds()
        return ProwResource(full_name, build_id, organization, repo, branch, variant, job_duration)

    @property
    def name(self):
        if self.__name:
            return self.__name

        prefix = f"periodic-ci-{self.org}-{self.repo}-{self.branch}-{self.variant + '-' if self.variant else ''}"
        self.__name = self.full_name.replace(prefix, "")
        return self.__name


class ProwJobFailure:
    BASE_STORAGE_URL = f"https://storage.googleapis.com/{consts.CI_BUCKET_NAME}/logs/"
    MAIN_PAGE_URL = f"https://prow.ci.openshift.org/view/gs/{consts.CI_BUCKET_NAME}/logs"
    DIRS_STORAGE_URL = f"https://gcsweb-ci.apps.ci.l2s4.p1.openshiftapps.com/gcs/{consts.CI_BUCKET_NAME}/logs/"
    MIN_FILE_SIZE = 4

    def __init__(self, failure_link: str, message_ts: str) -> None:
        """Initialization in this object is asynchronous - tot create new ProwResource call:
        prow_resources = await ProwResource(link).load()
        """
        self._raw_link = failure_link
        self._storage_link = ""
        self._message_ts = message_ts
        self._resource: Optional[ProwResource] = None
        self._job_steps = {}

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

        logger.debug(f"Get file content from {file_path} with base storage link {storage_link}")
        storage_link = storage_link + "/" if not storage_link.endswith("/") else storage_link
        full_file_url = urljoin(storage_link, file_path)
        logger.info(f"Opening a session to {full_file_url} ...")
        if (content := await Utils.get_file_content(full_file_url)) is not None:
            return content

        return None

    @AsyncTTL(time_to_live=86400, maxsize=1024, skip_args=1)
    async def _parse_files_grid(self, dir_path: str, build_id: str) -> List[Tuple[str, int]] | None:
        dir_content = await self.get_content(
            dir_path,
            self._storage_link.replace(self.BASE_STORAGE_URL, self.DIRS_STORAGE_URL),
        )

        if not dir_content:
            logger.error(f"Empty dir {dir_path} content on {build_id}. Please check directory path or if prow is up.")
            return None

        # Find all grid rows
        files = []
        if dir_content is None:
            logger.warning(f"Trying to parse none dir content for {dir_path}")
            return files

        soup = BeautifulSoup(dir_content, "html.parser")
        grid_rows = soup.select(".resource-grid .grid-row")

        for row in grid_rows:
            name_div = row.select_one(".pure-u-2-5 a")
            if name_div:  # Check to ensure there's an anchor tag within the div
                file = name_div.text.strip()  # Extract file name
                size = row.select_one(".pure-u-1-5").text.strip()  # Extract file size
                if file == "..":
                    continue

                if size == "-":
                    size = 0

                files.append((file, int(size)))

        return files

    @AsyncTTL(time_to_live=86400, maxsize=1024, skip_args=1)
    async def glob(self, dir_path: str, result: dict) -> Tuple[Optional[str], Optional[str]]:
        if dir_path.endswith("*"):
            dir_path = dir_path[:-1]

        files = await self._parse_files_grid(dir_path, self._resource.build_id)
        if files is None:
            return None, None

        for file, file_size in files:
            file_path = urljoin(dir_path, file)
            if file_size > consts.MAX_FILE_SIZE:
                continue
            content = await self.get_content(file_path, self._storage_link)
            contains = result.get("contains")
            if contains and content and contains in content:
                return result.get("emoji"), result.get("text")

        return None, None

    async def _update_actions(
        self, file_path: str, contains: str, failed_step: str, config_entry: dict, ignore_others: bool
    ) -> List[Action]:
        reaction = comment = None
        is_applied = False
        actions = list()

        description = config_entry.get("description", "")
        action_id = config_entry.get("action_id", None)

        if failed_step:
            reaction, comment = config_entry.get("emoji"), config_entry.get("text")
            is_applied = True

        elif "job_name" in config_entry and (
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
            action = Action(action_id, description, self._message_ts, ignore_others=ignore_others)
            action.reaction = Reaction(emoji=reaction) if reaction else None
            action.comment = Comment(text=comment, type=CommentType.ERROR_INFO, parse="full") if comment else None
            actions.append(action)

        if is_applied and "assignees" in config_entry:
            actions += self._apply_assignee_actions(config_entry, action_id, description)  # assignee inside action

        return actions

    def _apply_assignee_actions(self, config_entry: dict, action_id: str, description: str) -> List[Action]:
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
            action.comment = Comment(text=comment, type=CommentType.ASSIGNEE, parse="full")
            actions.append(action)

    @classmethod
    def _join_comments(cls, comments: Set[Comment]) -> Comment:
        comment_text = "\n".join([comment.text for comment in sorted(comments, key=lambda c: c.type.value)])
        return Comment(text=comment_text, type=CommentType.ERROR_INFO, parse="all")

    async def _get_job_actions(self, channel_config: ChannelFileConfig, filter_id: str = None) -> List[Action]:
        """
        :param channel_config:
        :param filter_id: Action filter id as defined in the configuration file
        :return:
        """
        actions = list()

        for action_data in channel_config.actions_items():
            try:
                if filter_id and (action_data.get("action_id") is None or action_data.get("action_id") != filter_id):
                    continue

                ignore_others = action_data.get("ignore_others", None)

                failed_step = ""
                if self._job_steps:
                    failed_steps = [step for step, step_data in self._job_steps.items() if not step_data["passed"]]
                    is_step_failed = action_data.get("step_name", "") in failed_steps
                    failed_step = action_data.get("step_name", "") if is_step_failed else ""

                conditions = action_data.get(
                    "conditions",
                    [
                        {
                            "contains": action_data.get("contains", ""),
                            "file_path": action_data.get("file_path", ""),
                            "failed_step": failed_step,
                        }
                    ],
                )

                for condition in conditions:
                    added_actions = await self.format_and_update_actions(
                        **condition,
                        config_entry=action_data,
                        ignore_others=ignore_others,
                    )
                    if added_actions:
                        actions += added_actions
                        if ignore_others:
                            return actions

            except UnicodeDecodeError as e:
                logger.error(f"{e}, Action data: {action_data}")

        return actions

    async def format_and_update_actions(
        self,
        file_path: str,
        contains: str,
        config_entry: dict,
        failed_step: str,
        ignore_others: bool,
    ) -> List[Action]:
        if not failed_step and (not file_path or not contains):
            return []

        if "{job_name}" in file_path:
            file_path = file_path.format(job_name=self.job_name)

        return await self._update_actions(file_path, contains, failed_step, config_entry, ignore_others)

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
        await self._set_job_steps()
        return self

    async def _set_job_steps(self):
        base_path = f"artifacts/{self.job_name}"
        steps_dir = await self._parse_files_grid(base_path, self._resource.build_id)

        job_steps = {}
        for step, _ in steps_dir:
            content = await self.get_content(f"{base_path}/{step}finished.json", self._storage_link)
            if not content:
                logger.warning(f"Can't find content for url='{self._storage_link}/{base_path}/{step}finished.json'")
                continue

            step_name = step[:-1] if step.endswith("/") else step
            job_steps[step_name] = json.loads(content)
            job_steps[step_name]["step_url"] = f"{self._storage_link}{base_path}/{step}"

        self._job_steps = {t[0]: t[1] for t in sorted(job_steps.items(), key=lambda tup: tup[1].get("timestamp"))}

    async def get_generic_action(self):
        jobs_history = await Utils.get_job_history(self._resource.full_name)
        last_seven_jobs = [j for j in jobs_history if (datetime.now() - timedelta(days=7)).date() <= j.started.date()]
        last_three_jobs = [j for j in jobs_history if (datetime.now() - timedelta(days=3)).date() <= j.started.date()]

        msg = f"<{self._raw_link} | {('=' * 3)} {self._resource.name} {('=' * 3)}>\n"
        msg += (
            f" {u'•'} Job failed after {Utils.get_formatted_duration(self._resource.job_duration)}.\n"
            f" {await self.get_formatted_failed_steps()}"
            f"{await self.get_cluster_formatted_links()}"
            f" \n*History:*\n"
            f"``` {u'•'} Number of job failures in the last 3 days: "
            f"{len([j for j in last_three_jobs if not j.succeeded])}\n"
            f" {u'•'} Number of job failures in the last 7 days: "
            f"{len([j for j in last_seven_jobs if not j.succeeded])}```\n"
            f" Job history can be found <{Utils.get_job_history_link(self._resource.full_name)} | *_here_*>\n"
        )
        msg += "\n"

        return Action("", "", self._message_ts, Comment(text=msg, type=CommentType.DEFAULT_COMMENT))

    async def get_test_infra_metadata(self) -> (List[ClusterDirData], str):
        """Collect job clusters important files that needed for the generic the action"""

        clusters_dir = []
        build_id = self._resource.build_id
        common_gather_path = f"artifacts/{self.job_name}/assisted-common-gather/artifacts/"
        directories = [d for d, size in await self._parse_files_grid(common_gather_path, build_id) if size == 0]

        for directory in directories:
            try:
                cluster_data = ClusterDirData()
                for file, _ in await self._parse_files_grid(f"{common_gather_path}{directory}", build_id):
                    if file == "metadata.json":
                        cluster_data.metadata = f"{common_gather_path}{directory}{file}"
                    elif file == "must-gather.tar":
                        cluster_data.must_gather = f"{common_gather_path}{directory}{file}"
                    elif file == "events.html":
                        cluster_data.events = f"{common_gather_path}{directory}{file}"
                    elif file.startswith("cluster_") and file.endswith("_logs.tar"):
                        cluster_data.cluster_logs = f"{common_gather_path}{directory}{file}"
                        cluster_data.cluster_id = file.split("_")[1]

                for file, _ in await self._parse_files_grid(f"{common_gather_path}{directory}cluster_files/", build_id):
                    if file == "install-config.yaml":
                        cluster_data.install_config = f"{common_gather_path}{directory}cluster_files/{file}"
                        break

                if cluster_data.cluster_id is not None:
                    clusters_dir.append(cluster_data)
            except TypeError:
                pass

        return clusters_dir, f"{common_gather_path}test_infra.log"

    def __get_file_link(self, file_path: str):
        return (self._storage_link + file_path).replace(self.BASE_STORAGE_URL, self.DIRS_STORAGE_URL)

    async def get_formatted_failed_steps(self) -> str:
        """Generate and return a formatted string list of all the job failed steps and link to each step directory"""
        job_steps = self._job_steps.items()
        failed_steps = [(step, v) for step, v in job_steps if not v.get("passed")]
        formatted_failed_steps = ""

        if len(failed_steps) > 0:
            formatted_failed_steps = "\n  - ".join(
                [
                    f"<{v.get('step_url').replace(self.BASE_STORAGE_URL, self.DIRS_STORAGE_URL)} | *_{step}_*>"
                    for step, v in failed_steps
                ]
            )
            formatted_failed_steps = f"{u'•'} *Failed on steps:*\n  - {formatted_failed_steps}\n"

        return formatted_failed_steps

    async def get_cluster_formatted_links(self) -> str:
        """
        Generate and return a formatted string that contains links to some of the cluster resources.
        Current resources are: install-config, cluster metadata, cluster logs (downloadable tar),
        must-gather (downloadable tar), cluster events (html link).
        """
        clusters_data, test_infra_log = await self.get_test_infra_metadata()
        if len(clusters_data) == 0:
            return ""

        res = f" {u'•'} *test-infra log* - <{self.__get_file_link(test_infra_log)} | link>\n"
        res += f"\n*Found {len(clusters_data)} clusters*:\n"
        i = 1
        for data in clusters_data:
            res += f" {i}) Cluster *_{data.cluster_id}_*:\n"
            if data.install_config is not None:
                res += f" {u'•'} `Install-config` - <{self.__get_file_link(data.install_config)} | *_link_*>\n"
            if data.metadata is not None:
                res += f" {u'•'} `Cluster metadata` - <{self.__get_file_link(data.metadata)} | *_link_*>\n"
            if data.cluster_logs is not None:
                res += f" {u'•'} `Cluster logs` - <{self.__get_file_link(data.cluster_logs)} | *_download link_*>\n"
            if data.must_gather is not None:
                res += f" {u'•'} `Must gather` - <{self.__get_file_link(data.must_gather)} | *_download link_*>\n"
            if data.events is not None:
                res += f" {u'•'} `Cluster events` - <{self.__get_file_link(data.events)} | *_link_*>\n"

            i += 1

        return res
