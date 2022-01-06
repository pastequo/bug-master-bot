from sqlalchemy import Column, String, Boolean

from .base import BaseModule


class Channel(BaseModule):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    is_private = Column(Boolean)
