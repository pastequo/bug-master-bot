import datetime
from typing import List

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import relationship

from .base import BaseModule


class MessageEvent(BaseModule):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_id = Column(String, index=True, nullable=False)
    job_name = Column(String, index=True, nullable=False)
    user = Column(String, index=True)
    url = Column(String, nullable=False)
    thread_ts = Column(Integer, index=True)
    time = Column(DateTime, default=datetime.datetime.now())
    channel_ts = Column(Float, index=True)

    channel_id = Column(String, ForeignKey("channels.id"), nullable=False)
    channel = relationship("Channel", foreign_keys=[channel_id])

    def __str__(self):
        return f"{self.id}, {self.job_id}, {self.user}, {self.channel}, {self.url}"

    @classmethod
    def select(cls, channel: str, since: datetime.date) -> List["MessageEvent"]:
        try:
            with cls.get_session() as session:
                return session.query(cls).order_by(cls.time).filter(cls.channel_id == channel, cls.time >= since).all()
        except NoResultFound:
            return []
