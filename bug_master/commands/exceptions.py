class NotSupportedCommandError(Exception):
    def __init__(self, message, command: str = ""):
        super().__init__(self, message)
        self.command = command
        self.message = message
