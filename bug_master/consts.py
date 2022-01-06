import os
import sys

from loguru import logger

APP_TOKEN = os.getenv("APP_TOKEN")
SIGNING_SECRET = os.getenv("SIGNING_SECRET")
BOT_USER_TOKEN = os.getenv("BOT_USER_TOKEN")
WEBSERVER_PORT = int(os.getenv("WEBSERVER_PORT", 8080))
WEBSERVER_HOST = os.getenv("WEBSERVER_HOST", default="0.0.0.0")

if APP_TOKEN is None:
    raise EnvironmentError("Missing app token environment variable")
if SIGNING_SECRET is None:
    raise EnvironmentError("Missing signing secret environment variable")
if BOT_USER_TOKEN is None:
    raise EnvironmentError("Missing bot user token environment variable")

logger.remove()
logger.add(sys.stdout, colorize=True, format="<green>{time:HH:mm:ss}</green> | {level} | <level>{message}</level>")
