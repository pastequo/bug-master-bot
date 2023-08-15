from abc import ABC

from bug_master.bug_master_bot import BugMasterBot


class InteractiveMessage(ABC):
    def __init__(self, bot: BugMasterBot) -> None:
        self._bot = bot
