import re
from typing import List

from bug_master.channel_config_handler import ChannelFileConfig
from bug_master.consts import logger
from bug_master.interactive.drop_down_menus.drop_down_interactive import (
    DropDownInteractive,
)
from bug_master.utils import Utils


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
    async def _get_options(cls, channel_config: ChannelFileConfig) -> List[dict]:
        options = []
        logger.info(
            f"Attempting to get jobs prow_configurations: {channel_config.prow_configurations}"
        )
        for job in await Utils.get_jobs(channel_config.prow_configurations):
            text = re.split("(?=e2e)", job).pop()
            options.append({"text": text, "value": job})

        return options
