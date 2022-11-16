import re
from typing import List

from cache import AsyncTTL

from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.utils import Utils

from .drop_down_interactive import DropDownInteractive


class JobsDropDown(DropDownInteractive):
    @classmethod
    def list_name(cls) -> str:
        return "jobs_list"

    @classmethod
    def text_box_info_text(cls) -> str:
        return "Pick a job..."

    @classmethod
    def drop_down_title(cls) -> str:
        return "Select a job for more info"

    @classmethod
    def callback_id(cls) -> str:
        return "jobs_interactive_menu"

    @classmethod
    @AsyncTTL(time_to_live=3600, maxsize=None)
    async def get_jobs(cls, channel_config: ChannelFileConfig):
        jobs = []
        config = channel_config.prow_configurations
        repo = config.get("repo")
        owner = config.get("owner")

        for file_path in config.get("files", []):
            periodics_jobs_config = await Utils.get_git_content(repo=repo, owner=owner, path=file_path)
            _jobs_config = periodics_jobs_config.get("periodics", {})
            periodics_names = [job.get("name") for job in _jobs_config if job.get("name").endswith("periodic")]
            jobs += periodics_names

        return jobs

    @classmethod
    async def _get_options(cls, channel_config: ChannelFileConfig) -> List[dict]:
        options = []

        for job in await cls.get_jobs(channel_config):
            text = re.split("(?=e2e)", job).pop()
            options.append({"text": text, "value": job})

        return options
