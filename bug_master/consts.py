import logging
import os
import sys

from loguru import logger

APP_TOKEN = os.getenv("APP_TOKEN")
SIGNING_SECRET = os.getenv("SIGNING_SECRET")
BOT_USER_TOKEN = os.getenv("BOT_USER_TOKEN")
SSL_KEYFILE_PASSWORD = os.getenv("SSL_KEYFILE_PASSWORD")
WEBSERVER_PORT = int(os.getenv("WEBSERVER_PORT", 8080))
WEBSERVER_HOST = os.getenv("WEBSERVER_HOST", default="0.0.0.0")
SQLALCHEMY_DATABASE_PATH = os.getenv("SQLALCHEMY_DATABASE_PATH", default="./bot.db")
CONFIGURATION_FILE_NAME = os.getenv("CONFIGURATION_FILE_NAME", default="bug_master_configuration.yaml")
LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.DEBUG))

if APP_TOKEN is None:
    raise EnvironmentError("Missing app token (APP_TOKEN) environment variable")
if SIGNING_SECRET is None:
    raise EnvironmentError("Missing signing secret (SIGNING_SECRET) environment variable")
if BOT_USER_TOKEN is None:
    raise EnvironmentError("Missing bot user token (BOT_USER_TOKEN) environment variable")

logger.remove()
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:HH:mm:ss}</green> | {level} | <level>{message}</level>",
    level=LOG_LEVEL,
)

logger.info(f"Initialized logger and set level to be {logging.getLevelName(LOG_LEVEL)}")
