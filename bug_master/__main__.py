from . import consts
from .app import start_web_server


if __name__ == "__main__":
    start_web_server(port=consts.WEBSERVER_PORT, host=consts.WEBSERVER_HOST)
