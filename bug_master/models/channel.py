from sqlalchemy import Boolean, Column, String

from .base import BaseModule


class Channel(BaseModule):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    is_private = Column(Boolean)

    def __str__(self):
        return f"{self.id}, {self.name}, {self.is_private}"
