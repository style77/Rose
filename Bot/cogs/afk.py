import discord
from dataclasses import dataclass
from discord.ext import commands

from ..cogs.classes.other import Plugin


@dataclass
class AFKObject:
    user_id: int
    reason: str


class AFK(Plugin):
    async def is_afk(self, user_id):
        return await self.bot.pg_con.fetch("SELECT * FROM afk WHERE user_id = $1", user_id) is not None

    @staticmethod
    def __create_object(data):
        return AFKObject(data['user_id'], data['reason'])

    @commands.command()
    async def afk(self, ctx, *, reason: str):
        """Gdy ktoś cię oznaczy będąc afk, oznaczenie zostanie usunięte."""
        if self.is_afk(ctx.author.id):
            return await ctx.send(ctx.lang['already_afk'])
        await ctx.send(f"{ctx.author.mention} {ctx.lang['afk_from_now']}.")
        await self.bot.db.execute("INSERT INTO afk (user_id, reason) VALUES ($1, $2)", ctx.author.id, reason)

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.is_afk(message.author.id):
            if message.author.id == message.author.id:
                await message.channel.send(f"**{message.author}** już nie jest AFK.")
                await self.bot.db.execute("DELETE FROM afk WHERE user_id = $1", message.author.id)

        for member in message.mentions:

            data = await self.bot.db.fetch("SELECT * FROM afk WHERE user_id = $1", member.id)
            afk = self.__create_object(data)
            if not afk:
                continue
            await message.channel.send(f"{message.author.mention}, {self.bot.context.lang['dont_ping']} **{str(member)}**. {self.bot.context.lang['reason']}: `{afk.reason}`.")

            try:
                await message.delete()
            except discord.Forbidden:
                pass


def setup(bot):
    bot.add_cog(AFK(bot))
