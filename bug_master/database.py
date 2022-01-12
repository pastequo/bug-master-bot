import uuid
from contextlib import contextmanager
from typing import Type

from loguru import logger
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .consts import SQLALCHEMY_DATABASE_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLALCHEMY_DATABASE_PATH}"

logger.info(f"Creating database engine, {SQLALCHEMY_DATABASE_URL}")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(declarative_base()):
    __abstract__ = True

    @classmethod
    @contextmanager
    def get_session(cls) -> Session:
        db = None
        session_uuid = str(uuid.uuid4())
        try:
            logger.info(f"Creating a new database session - {session_uuid}")
            db = SessionLocal()
            cls.create_all()
            yield db
        finally:
            if db:
                logger.info(f"Closing database session - {session_uuid}")
                db.close()
                logger.info(f"Session {session_uuid} closed")

    @classmethod
    def create_all(cls):
        cls.metadata.create_all(bind=engine)


def create_model(session: Session, model: Type[Base], **kwargs):
    """Create or get if already exist"""
    instance = session.query(model).filter_by(**kwargs).first()

    if not instance:
        instance = model(**kwargs)
        session.add(instance)

    return instance
