import json
import logging
from typing import Callable
from urllib.parse import parse_qs

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute, APIRouter
from slack_sdk import signature
from starlette.responses import JSONResponse, StreamingResponse
from uvicorn_loguru_integration import run_uvicorn_loguru

from . import consts
from .bug_master_bot import BugMasterBot
from .commands import Command, CommandHandler, NotSupportedCommandError
from .consts import logger
from .events import EventHandler, UrlVerificationEvent


class ContextIncludedRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            response: Response = await original_route_handler(request)
            body = await request.body()
            headers = dict(request.headers)
            is_request_valid = signature_verifier.is_valid_request(body, headers)

            logger.debug(f"Got new request, {request.method} {request.url} {headers} {body}")
            if not is_request_valid:
                logger.warning(f"Got invalid request, {request.method} {headers} {request.url} {body}")
                return Response(
                    content=json.dumps({"code": "401", "message": "No proper authentication credentials"}),
                    status_code=401,
                    media_type="application/json",
                )

            # logger.debug(f"Got a valid request, {request.method} {request.url} {body}")
            if headers.get("content-type") == "application/x-www-form-urlencoded":
                return response

            return Response(
                content=json.dumps({"challenge": json.loads(body).get("challenge", "")}),
                status_code=response.status_code,
                media_type="application/json",
            )

        return custom_route_handler


app = FastAPI()
bot = BugMasterBot(consts.BOT_USER_TOKEN, consts.APP_TOKEN, consts.SIGNING_SECRET)
events_handler = EventHandler(bot)
commands_handler = CommandHandler(bot)
router = APIRouter(route_class=ContextIncludedRoute)
signature_verifier = signature.SignatureVerifier(consts.SIGNING_SECRET)


@app.middleware('http')
async def headers_middleware(request: Request, call_next: Callable):
    if not hasattr(request, "headers"):
        return JSONResponse(content={"message": "Invalid request"}, status_code=401)
    response: StreamingResponse = await call_next(request)
    return response


@router.post("/slack/config")
async def config(request: Request):
    body = {k.decode(): v.pop().decode() for k, v in parse_qs(await request.body()).items()}
    try:
        command = await commands_handler.get_command(body)
    except NotSupportedCommandError as e:
        return Command.get_response(f"{e}")

    return await command.handle()


@router.post("/slack/events")
async def events(request: Request):
    event = await events_handler.get_event(await request.json())
    if event is None or request.headers.get("x-slack-retry-num", False):
        logger.info(f"Skipping duplicate or unsupported event: {event}")
        return {"msg": "Success", "Code": 200}

    if isinstance(event, UrlVerificationEvent):
        logger.info("Url verification event - success")
        return {"status": 200, "challenge": event.challenge}

    channel_info = await event.get_channel_info()
    return await event.handle(channel_info=channel_info)


app.include_router(router)


def start_web_server(host: str, port: int):
    bot.start()
    uvicorn_config = uvicorn.Config(
        app=app, loop="asyncio", host=host, port=port, log_level=logging.getLevelName(consts.LOG_LEVEL).lower()
    )
    run_uvicorn_loguru(uvicorn_config)
