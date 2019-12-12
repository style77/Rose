import discord
from discord.ext import commands

from .classes.other import Plugin


class Social(Plugin):
    def __init__(self, bot):
        super().__init__(bot, command_attrs={'not_turnable': True})
        self.bot = bot

    @commands.command()
    async def support(self, ctx):
        # await ctx.send(f"{ctx.lang['join_us']} discord.gg/{self.bot._config['support']}")
        await ctx.send(f"discord.gg/{self.bot._config['support']}")

    @commands.command(aliases=['add', 'addbot', 'add_bot'])
    async def invite(self, ctx):
        msg = await ctx.send(discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(8)))
        try:
            await msg.add_reaction("\U00002764")
        except discord.HTTPException:
            pass


def setup(bot):
    bot.add_cog(Social(bot))
