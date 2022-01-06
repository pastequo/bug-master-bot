from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

SQLALCHEMY_DATABASE_URL = "sqlite:///./bot.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_session() -> Session:
    db = None
    try:
        db = SessionLocal()
        create_all()
        return db
    finally:
        if db:
            db.close()


def create_model(session: Session, model: Base, **kwargs):
    """ Create or get if already exist """
    instance = session.query(model).filter_by(**kwargs).first()

    if not instance:
        instance = model(**kwargs)
        session.add(instance)

    return instance


def create_all():
    Base.metadata.create_all(bind=engine)
