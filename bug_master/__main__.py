from . import consts
from .app import start_web_server


def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()

    if not instance:
        instance = model(**kwargs)
        session.add(instance)

    return instance


if __name__ == "__main__":
    start_web_server(port=consts.WEBSERVER_PORT, host=consts.WEBSERVER_HOST)
