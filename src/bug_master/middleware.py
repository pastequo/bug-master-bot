from typing import Callable

from fastapi.routing import APIRoute
from slack_sdk.signature import SignatureVerifier
from starlette.middleware.base import RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bug_master import consts

_signature_verifier = SignatureVerifier(consts.SIGNING_SECRET)


class SlackRequest(Request):
    async def body(self) -> bytes:
        if "body" in self.scope:
            setattr(self, "_body", self.scope.get("body"))

        elif not hasattr(self, "_body"):
            body = await super().body()
            setattr(self, "_body", body)

        return self._body


class SlackRoute(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            return await original_route_handler(SlackRequest(request.scope, request.receive))

        return custom_route_handler


async def validate_request(request):
    body = await request.body()
    headers = dict(request.headers) if hasattr(request, "headers") else {}

    is_request_valid = _signature_verifier.is_valid_request(body, headers)
    if not is_request_valid:
        consts.logger.warning(f"Got invalid request, {request.method} {headers} {request.scope} {body}")
        return None, None

    return body, headers


async def exceptions_middleware(request: Request, call_next: RequestResponseEndpoint) -> Response:
    try:
        body, headers = await validate_request(request)

        if headers is None:
            return JSONResponse(content={"message": "Invalid request"}, status_code=401)

        request.scope["body"] = body
        return await call_next(request)

    except BaseException as e:
        err = f"Internal server error - {e.__class__.__name__}: {e}"
        consts.logger.error(
            f"{err}, "
            f"Request: url: {request.url}, "
            f"headers: {request.headers}, "
            f"params: {request.query_params or dict()}"
        )

        return Response("Internal server error", status_code=500)
