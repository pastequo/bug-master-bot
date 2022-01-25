import datetime
from typing import Union

import yaml
from sqlalchemy import Column, DateTime, String
from sqlalchemy.exc import NoResultFound

from .base import BaseModule


class ChannelConfig(BaseModule):
    __tablename__ = "channel_configs"

    id = Column(String, primary_key=True, index=True, nullable=False)
    channel_id = Column(String, index=True, nullable=False)
    raw_configs = Column(String)
    time = Column(DateTime, default=datetime.datetime.now())

    def __str__(self):
        return f"{self.id}, {self.channel_id}, {self.is_private}"

    def update_config(self, config: dict):
        with self.get_session() as session:
            self.time = datetime.datetime.now()
            self.raw_configs = yaml.dump(yaml.safe_load(config), default_flow_style=False)
            session.add(self)
            session.commit()

    @classmethod
    def select(cls, channel_id: str) -> Union["ChannelConfig", None]:
        try:
            with cls.get_session() as session:
                return session.query(cls).order_by(cls.time).filter(cls.id == channel_id).one()
        except NoResultFound:
            return None
