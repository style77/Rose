import discord
from discord.ext import commands

class Context(commands.Context):
    def __init__(self, **kwargs):
        self._db = None

    async def release(self):
        if self._db is not None:
            await self.bot.pg_con.release(self._db)
            self._db = None
