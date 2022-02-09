from dataclasses import dataclass


@dataclass
class Comment:
    text: str
    parse: str = "none"

    def __eq__(self, other: "Comment"):
        return self.text == other.text

    def __hash__(self):
        return hash(self.text)
