import discord
from discord.ext import commands

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def afk(self, ctx, *, reason: str=None):
        """Gdy ktoś cię oznaczy będąc afk, oznaczenie zostanie usunięte."""
        if not reason:
            return await ctx.send(_(ctx.lang, "Podaj powód bycia afk."))
        await ctx.send(_(ctx.lang, "**{author}** jest od teraz afk.").format(author=ctx.author))
        await self.bot.pg_con.execute("INSERT INTO afk (user_id, reason) VALUES ($1, $2)", ctx.author.id, reason)

    @commands.Cog.listener()
    async def on_message(self, message):
        afkchecker = await self.bot.pg_con.fetch("SELECT * FROM afk WHERE user_id = $1", message.author.id)
        if afkchecker:
            author = self.bot.get_user(afkchecker[0]['user_id'])
            if message.author.id == author.id:
                await message.channel.send(_(await get_language(self.bot, message.guild.id), "**{author}** już nie jest AFK.").format(author=message.author))
                await self.bot.pg_con.execute("DELETE FROM afk WHERE user_id = $1", author.id)
        n = 0
        for c in message.mentions:
            afk = await self.bot.pg_con.fetch("SELECT * FROM afk WHERE user_id = $1", message.mentions[n].id)
            if afk:
                user = self.bot.get_user(afk[0]['user_id'])
                if afk and message.mentions[n].id == afk[0]['user_id']:
                    await message.channel.send(_(await get_language(self.bot, message.guild.id), "Nie oznaczaj **{user}**. Jest on afk, {reason}.").format(user=user.name, reason=afk[0]['reason']))
                    await message.delete()
            n += 1


def setup(bot):
    bot.add_cog(AFK(bot))
