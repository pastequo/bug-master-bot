import logging

import uvicorn
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from uvicorn_loguru_integration import run_uvicorn_loguru

from . import consts
from .bug_master_bot import BugMasterBot
from .commands import CommandHandler
from .events import EventHandler

app = FastAPI()
bot = BugMasterBot(consts.BOT_USER_TOKEN, consts.APP_TOKEN, consts.SIGNING_SECRET)
events_handler = EventHandler(bot)
commands_handler = CommandHandler(bot)


async def exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except BaseException as e:
        err = f"Internal server error - {e.__class__.__name__}: {e}"
        consts.logger.error(f"{err}, "
                            f"Request: url: {request.url}, "
                            f"headers: {request.headers}, "
                            f"params: {request.query_params or dict()}"
                            )

        return Response(err, status_code=500)


def start_web_server(host: str, port: int):
    from .routes import init_routes

    app.middleware("http")(exceptions_middleware)
    init_routes()
    bot.start()
    uvicorn_config = uvicorn.Config(
        app=app, loop="asyncio", host=host, port=port, log_level=logging.getLevelName(consts.LOG_LEVEL).lower()
    )
    run_uvicorn_loguru(uvicorn_config)
