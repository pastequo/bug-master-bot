import json
from typing import Tuple, Union
from urllib.parse import parse_qs

from slack_sdk import signature
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from . import consts
from .app import app, commands_handler, events_handler
from .commands import Command, NotSupportedCommandError
from .consts import logger
from .events import Event, UrlVerificationEvent

_signature_verifier = signature.SignatureVerifier(consts.SIGNING_SECRET)


async def validate_request(request) -> Tuple[bytes, dict, Union[Response, None]]:
    body = await request.body()
    headers = dict(request.headers) if hasattr(request, "headers") else {}

    is_request_valid = _signature_verifier.is_valid_request(body, headers)
    if not is_request_valid:
        logger.warning(f"Got invalid request, {request.method} {headers} {request.url} {body}")
        return body, headers, JSONResponse(content={"message": "Invalid request"}, status_code=401)

    return body, headers, None


async def validate_event_request(request) -> Tuple[Union[Event, None], Union[Response, None]]:
    body, headers, not_valid_response = await validate_request(request)
    if not_valid_response:
        return None, not_valid_response

    event = await events_handler.get_event(await request.json())  # json.loads(body)

    if event is None or request.headers.get("x-slack-retry-num", False):
        logger.info(f"Skipping duplicate or unsupported event: {event}")
        return None, JSONResponse({"msg": "Success", "Code": 200})

    if isinstance(event, UrlVerificationEvent):
        logger.info("Url verification event - success")
        return None, JSONResponse(
            content=json.dumps({"challenge": json.loads(body).get("challenge", "")}),
            status_code=200,
            media_type="application/json",
        )

    if event.is_command_message():
        logger.info(f"Skipping command message event {event}")
        return None, JSONResponse({"msg": "Success", "Code": 200})

    return event, None


@app.post("/slack/events")
async def events(request: Request):
    event, response = await validate_event_request(request)
    if event is None:
        return response

    channel_info = await event.get_channel_info()
    return await event.handle(channel_info=channel_info)


@app.post("/slack/commands")
async def commands(request: Request):
    raw_body, headers, not_valid_response = await validate_request(request)
    if not_valid_response:
        return None, not_valid_response

    body = {k.decode(): v.pop().decode() for k, v in parse_qs(raw_body).items()}
    try:
        command = await commands_handler.get_command(body)
    except NotSupportedCommandError as e:
        return Command.get_response(f"{e}")

    return await command.handle()


def init_routes():
    logger.info("Web server routes initialized successfully")
