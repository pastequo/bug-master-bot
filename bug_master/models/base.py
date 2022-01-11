import sqlite3
from typing import Union

from sqlalchemy.exc import PendingRollbackError

from bug_master.database import Base

from ..consts import logger


class BaseModule(Base):
    __abstract__ = True

    @classmethod
    def create(cls, **kwargs) -> Union[Base, None]:
        """Create or get if already exist"""
        # session: Session = cls.get_session()
        with cls.get_session() as session:
            _id = kwargs.get("id", "")
            try:
                instance = session.query(cls).filter_by(id=_id).first()
            except PendingRollbackError:
                session.rollback()
                _id = kwargs.get("id", "")
                instance = session.query(cls).filter_by(id=_id).first()
            except sqlite3.OperationalError as e:
                logger.error(f"Database error, {e}")
                return None
            except Exception as e:
                logger.error(f"Database error, {e}")
                return None

            if not instance:
                instance = cls(**kwargs)
                session.add(instance)
                session.commit()
                logger.info(f"Added new entry to `{cls.__tablename__}` table, with id {instance.id}")

        return instance
