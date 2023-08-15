from bug_master.interactive.drop_down_menus import (
    DaysRangeDropDown,
    DropDownInteractive,
    JobsDropDown,
)


class InteractiveFlowHandler:
    __interactive = {
        DaysRangeDropDown.callback_id(): DaysRangeDropDown,
        JobsDropDown.callback_id(): JobsDropDown,
    }

    @classmethod
    def get_next(cls, callback_id: str) -> DropDownInteractive:
        return cls.__interactive.get(callback_id)
