import re
import zlib

import discord
from discord.ext import commands

from .classes.other import Plugin


class Social(Plugin):
    def __init__(self, bot):
        super().__init__(bot, command_attrs={'not_turnable': True})
        self.bot = bot

    @commands.command()
    async def support(self, ctx):
        return await ctx.send(f"{ctx.lang['join_us']} discord.gg/{self.bot._config['support']}")


def setup(bot):
    bot.add_cog(Social(bot))
