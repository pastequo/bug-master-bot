import asyncio
import json
from typing import Tuple, Union
from urllib.parse import parse_qs

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .app import app, bot, commands_handler, events_handler
from .commands import Command, NotSupportedCommandError
from .consts import logger
from .events import Event, UrlVerificationEvent
from .interactive import InteractiveResponse


class RouteValidator:
    @classmethod
    async def validate_event_request(cls, request) -> Tuple[Union[Event, None], Union[Response, None]]:
        body = await request.body()

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


async def handle_event_exception(event: Event, **kwargs):
    try:
        await event.handle(**kwargs)
    except BaseException as e:
        err = f"Got error while handled event {{{event}}}, {e.__class__.__name__} {e}"
        logger.error(err)
        if event.user_id:
            await bot.add_comment(event.user_id, err)


async def handle_command_exception(command: Command) -> Response:
    try:
        return await command.handle()
    except BaseException as e:
        err = f"Got error while handled command {{{command}}}, {e.__class__.__name__} {e}"
        logger.error(err)

    await bot.add_comment(channel=command.user_id, comment=err)
    return command.get_response("Internal server error. See BugMaster private chat for more information.")


@app.post("/slack/events")
async def events(request: Request):
    event, response = await RouteValidator.validate_event_request(request)
    if event is None:
        return response

    logger.debug(f"Got new event - {event}")
    if not (channel_info := await event.get_channel_info()):
        logger.error(f"Invalid event {event}, {event._data}")
        return JSONResponse({"msg": "Failure", "Code": 401})

    asyncio.get_event_loop().create_task(handle_event_exception(event, channel_info=channel_info))
    return JSONResponse({"msg": "Success", "Code": 200})


@app.post("/slack/commands/{command}")
@app.post("/slack/commands")
async def commands(request: Request, command: str = None):
    raw_body = await request.body()

    logger.info("Handling new command")
    body = {k.decode(): v.pop().decode() for k, v in parse_qs(raw_body).items()}
    if command:
        body["text"] = command
    try:
        command = await commands_handler.get_command(body)
    except NotSupportedCommandError as e:
        logger.warning(f"Failed to get command, {e.command}")
        return Command.get_response(f"{e.message}")

    return await handle_command_exception(command)


@app.post("/slack/interactive")
async def interactive(request: Request):
    raw_body = await request.body()
    payload = {k.decode(): json.loads(v.pop().decode()) for k, v in parse_qs(raw_body).items()}.get("payload")
    return await InteractiveResponse(bot, payload).get_next_response()


def init_routes():
    logger.info("Web server routes initialized successfully")
