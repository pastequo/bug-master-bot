from dataclasses import dataclass
from enum import Enum


class CommentType(Enum):
    ERROR_INFO = "0"
    ASSIGNEE = "1"
    MORE_INFO = "2"
    DEFAULT_COMMENT = "3"


@dataclass
class Comment:
    text: str
    type: CommentType
    parse: str = "none"

    def __eq__(self, other: "Comment"):
        return self.text == other.text

    def __hash__(self):
        return hash(self.text)

    def __str__(self):
        return self.text


@dataclass
class Reaction:
    emoji: str

    def __hash__(self):
        return hash(self.emoji)

    def __str__(self):
        return self.emoji


@dataclass
class Action:
    id: str
    description: str
    message_id: str
    comment: Comment = None
    reaction: Reaction = None
    ignore_others: bool = False
