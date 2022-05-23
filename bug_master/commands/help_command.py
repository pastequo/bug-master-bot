from typing import Dict

from loguru import logger
from starlette.responses import Response

from .. import consts
from .command import Command


class HelpCommand(Command):
    @classmethod
    def get_arguments_info(cls) -> Dict[str, str]:
        return {}

    @classmethod
    def get_description(cls) -> str:
        return "More information about how to use Bot Master"

    @classmethod
    def get_commands_info(cls) -> str:
        from .supported_commands import SupportedCommands

        commands_map = SupportedCommands.get_commands_map()
        commands_info = []

        i = 1
        for cmd, cmd_cls in commands_map.items():
            if not cmd_cls.is_enabled():
                continue

            command_str = [f"{i}. {cmd} - {cmd_cls.get_description()}"]

            for argument, arg_info in cmd_cls.get_arguments_info().items():
                command_str += [f"\t{u'•'} {argument}: {arg_info}"]

            commands_info.append("\n".join(command_str))
            i += 1

        disabled_commands = list(SupportedCommands.get_disabled_commands_map().keys())
        disabled_commands_str = f"* Disabled Commands: {','.join(disabled_commands)}"

        return "\n".join(commands_info) + f"\n{disabled_commands_str}"

    async def handle(self) -> Response:
        logger.info(f"Handling {self._command}")

        return self.get_response(
            f"*============== Help ==============*\n"
            f"*Available commands:*\n"
            f"```{self.get_commands_info()}```\n\n"
            f"*Configuration file:*\n"
            f"Bot configuration file, a declarative yaml file that defines the channel actions for "
            f"each job failure entry. The configuration file name must be named"
            f" `{consts.CONFIGURATION_FILE_NAME}`.\n"
            f"Each job failure must start with :red_jenkins_circle: emoji.\n"
            f"For each action (job failure) this are the following arguments:\n"
            f"``` 1. description  - Description of the failure.\n"
            f" 2. emoji - Reaction to add to the thread on case of match (If empty or missing no reaction "
            f"is posted).\n"
            f" 3. text -  Comment to add to thread on case of match (If empty or missing, no comment is posted)\n"
            f" 4. contains - String that indicates the failure, checks if any files content that listed on "
            f"`file_path` contains that given string.\n"
            f" 6. file_path - File or directory to search for match in it. The path is relative to PROW job"
            f" (starting with artifacts). To specify a directory just set file name to be *.\n"
            f" 7. job_name - Apply action if the job name start with (note that the job name is defined by the "
            f"name on release branch).\n"
            f" 8. assignees - Assign users to specific failure (see /bugmaster config schema for more info).```\n"
        )
