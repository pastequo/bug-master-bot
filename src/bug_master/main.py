from bug_master import consts
from bug_master.app import start_web_server


def main():
    start_web_server(port=consts.WEBSERVER_PORT, host=consts.WEBSERVER_HOST)


if __name__ == "__main__":
    main()
