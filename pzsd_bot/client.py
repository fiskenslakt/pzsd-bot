import aiohttp


class Client:
    def __init__(self):
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
