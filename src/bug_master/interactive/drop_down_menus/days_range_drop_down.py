from typing import List

from bug_master.interactive.drop_down_menus.drop_down_interactive import DropDownInteractive


class DaysRangeDropDown(DropDownInteractive):
    @classmethod
    def drop_down_title(cls) -> str:
        return "Since when do you want to get the status?"

    @classmethod
    def color(cls) -> str:
        return "#4ae370"

    @classmethod
    def callback_id(cls) -> str:
        return "date_range_interactive_menu"

    @classmethod
    def list_name(cls) -> str:
        return "date_range_list"

    @classmethod
    def text_box_info_text(cls) -> str:
        return "Date range"

    @classmethod
    async def _get_options(cls, job_name: str) -> List[dict]:
        return [
            {"text": "Last day", "value": "1|" + job_name},
            {"text": "Last 3 days", "value": "3|" + job_name},
            {"text": "Last 1 week", "value": "7|" + job_name},
            {"text": "Last 2 weeks", "value": "14|" + job_name},
        ]
