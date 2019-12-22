import discord
from dataclasses import dataclass
from discord.ext import commands

from .classes.other import Plugin
from .utils import get_language


@dataclass
class AFKObject:
    user_id: int
    reason: str


class AFK(Plugin):
    async def is_afk(self, user_id):
        z = await self.bot.db.fetchrow("SELECT * FROM afk WHERE user_id = $1", user_id)
        return z is not None

    @staticmethod
    def __create_object(data):
        return AFKObject(data['user_id'], data['reason'])

    @commands.command()
    async def afk(self, ctx, *, reason: str):
        """Gdy ktoś cię oznaczy będąc afk, oznaczenie zostanie usunięte."""
        if await self.is_afk(ctx.author.id):
            return await ctx.send(ctx.lang['already_afk'])
        await ctx.send(f"{ctx.author.mention} {ctx.lang['afk_from_now']}.")
        await self.bot.db.execute("INSERT INTO afk (user_id, reason) VALUES ($1, $2)", ctx.author.id, reason)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        lang_ = await get_language(self.bot, message.guild)
        lang = self.bot.get_language_object(lang_)

        if await self.is_afk(message.author.id):
            await message.channel.send(f"{message.author.mention}, {self.bot.context.lang['no_longer_afk']}.")
            await self.bot.db.execute("DELETE FROM afk WHERE user_id = $1", message.author.id)

        for member in message.mentions:

            data = await self.bot.db.fetchrow("SELECT * FROM afk WHERE user_id = $1", member.id)
            if not data:
                continue
            afk = self.__create_object(data)
            await message.channel.send(f"{message.author.mention}, {self.bot.context.lang['dont_ping']} **{str(member)}**. {self.bot.context.lang['reason']}: `{afk.reason}`.")

            try:
                await message.delete()
            except discord.Forbidden:
                pass


def setup(bot):
    bot.add_cog(AFK(bot))
