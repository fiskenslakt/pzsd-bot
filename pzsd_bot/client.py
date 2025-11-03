import logging
from asyncio import sleep

from aiohttp import ClientHandlerType, ClientRequest, ClientResponse, ClientSession

logger = logging.getLogger(__name__)


class Client:
    def __init__(self):
        self.session: ClientSession | None = None

    async def start(self):
        if self.session is None or self.session.closed:
            self.session = ClientSession()

    async def close(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()


async def retry_middleware(
    req: ClientRequest, handler: ClientHandlerType
) -> ClientResponse:
    for _ in range(3):
        resp = await handler(req)
        if resp.ok:
            return resp
        logger.info("Request failed, retrying...")
        await sleep(1)
    return resp
