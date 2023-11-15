from discord.ext import tasks


class Database:
    def __init__(self, bot, poll):
        self.bot = bot
        self.poll = poll

        self._poll_query = []

    @tasks.loop(seconds=1)
    async def bulk_inserting(self):
        for query in self._poll_query:
            try:
                await query
            except Exception as e:
                print(e)

    @bulk_inserting.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    async def execute(self, query: str, *args, timeout: float=None, queue=False):
        if queue:
            self._poll_query.append(self.poll.execute(query, *args, timeout=timeout))
        else:
            return await self.poll.execute(query, *args, timeout=timeout)

    async def fetch(self, query, *args, timeout=None, queue=False):
        if queue:
            self._poll_query.append(self.poll.fetch(query, *args, timeout=timeout))
        else:
            return await self.poll.fetch(query, *args, timeout=timeout)

    async def fetchrow(self, query, *args, timeout=None, queue=False):
        if queue:
            self._poll_query.append(self.poll.fetchrow(query, *args, timeout=timeout))
        else:
            return await self.poll.fetchrow(query, *args, timeout=timeout)

    async def fetchval(self, query, *args, column=0, timeout=None, queue=False):
        if queue:
            self._poll_query.append(self.poll.fetchval(query, *args, column=column, timeout=timeout))
        else:
            return await self.poll.fetchval(query, *args, column=column, timeout=timeout)

    async def executemany(self, command: str, args, *, timeout: float=None, queue=False):
        if queue:
            self._poll_query.append(self.poll.executemany(command, args, timeout=timeout))
        else:
            return await self.poll.executemany(command, args, timeout=timeout)
        