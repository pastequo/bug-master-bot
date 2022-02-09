from dataclasses import dataclass
from enum import Enum


class CommentType(Enum):
    ERROR_INFO = "0"
    ASSIGNEE = "1"
    MORE_INFO = "2"


@dataclass
class Comment:
    text: str
    type: CommentType
    parse: str = "none"

    def __eq__(self, other: "Comment"):
        return self.text == other.text

    def __hash__(self):
        return hash(self.text)
