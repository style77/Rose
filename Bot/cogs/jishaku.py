from discord import PartialEmoji
from datetime import datetime
import os
import asyncio

from discord.ext import commands
from jishaku import cog
from jishaku.exception_handling import attempt_add_reaction, do_after_sleep, send_traceback, ReplResponseReactor
import subprocess

FORWARD = PartialEmoji(animated=False, name="yessir", id=581621730372485131)
KAZ_HAPPY = PartialEmoji(
    animated=False, name="oke", id=581620536627560450)
ERR = PartialEmoji(
    animated=False, name="err", id=581620542042275846
)
SYNTAX = PartialEmoji(
    animated=False, name="syntax", id=581620540620537866
)

class AltReplReactor(ReplResponseReactor):
    async def __aenter__(self):
        self.handle = self.loop.create_task(do_after_sleep(
            1, attempt_add_reaction, self.message, FORWARD))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            self.handle.cancel()
        if not exc_val:
            await attempt_add_reaction(self.message, KAZ_HAPPY)
            return
        self.raised = True
        if isinstance(exc_val, (asyncio.TimeoutError, subprocess.TimeoutExpired)):
            await attempt_add_reaction(self.message, SYNTAX)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        elif isinstance(exc_val, SyntaxError):
            await attempt_add_reaction(self.message, SYNTAX)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        else:
            await attempt_add_reaction(self.message, ERR)
            await send_traceback(self.message.author, 8, exc_type, exc_val, exc_tb)
        return True


cog.JISHAKU_RETAIN = True
cog.ReplResponseReactor = AltReplReactor


class Jishaku(cog.Jishaku):
    def __init__(self, bot):
        super().__init__(bot)
        self.start_time = datetime.utcnow()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def eval(self, ctx, *, code):
        await ctx.invoke(self.bot.get_command('jishaku py'), argument=code)

def setup(bot):
    bot.add_cog(Jishaku(bot))
