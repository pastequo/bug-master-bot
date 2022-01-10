from contextlib import contextmanager
from typing import Type

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

from .consts import SQLALCHEMY_DATABASE_PATH

SQLALCHEMY_DATABASE_URL = f"sqlite:///{SQLALCHEMY_DATABASE_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(declarative_base()):
    __abstract__ = True

    @classmethod
    @contextmanager
    def get_session(cls) -> Session:
        db = None
        try:
            db = SessionLocal()
            cls.create_all()
            yield db
        finally:
            if db:
                db.close()

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
