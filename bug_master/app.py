import logging

import uvicorn
from fastapi import FastAPI
from uvicorn_loguru_integration import run_uvicorn_loguru

from . import consts
from .bug_master_bot import BugMasterBot
from .commands import CommandHandler
from .events import EventHandler

app = FastAPI()
bot = BugMasterBot(consts.BOT_USER_TOKEN, consts.APP_TOKEN, consts.SIGNING_SECRET)
events_handler = EventHandler(bot)
commands_handler = CommandHandler(bot)


def start_web_server(host: str, port: int):
    from .routes import init_routes

    init_routes()
    bot.start()
    uvicorn_config = uvicorn.Config(
        app=app, loop="asyncio", host=host, port=port, log_level=logging.getLevelName(consts.LOG_LEVEL).lower()
    )
    run_uvicorn_loguru(uvicorn_config)
