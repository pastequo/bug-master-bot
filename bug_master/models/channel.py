import datetime
from typing import Union

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.exc import NoResultFound

from .base import BaseModule


class Channel(BaseModule):
    __tablename__ = "channels"

    id = Column(String, primary_key=True, index=True, nullable=False)
    name = Column(String, index=True, nullable=False)
    is_private = Column(Boolean)
    time = Column(DateTime, default=datetime.datetime.now())

    def __str__(self):
        return f"{self.id}, {self.name}, {self.is_private}"

    @classmethod
    def select(cls, channel_id: str) -> Union["Channel", None]:
        try:
            with cls.get_session() as session:
                return session.query(cls).order_by(cls.time).filter(cls.id == channel_id).one()
        except NoResultFound:
            return None

    def update_last_seen(self):
        with Channel.get_session() as session:
            self.time = datetime.datetime.now()
            session.add(self)
            session.commit()
