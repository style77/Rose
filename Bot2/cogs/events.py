import discord
from discord.ext import commands

from .classes.other import Plugin


class Events(Plugin):

    @commands.Cog.listener()
    async def on_guild_remove(self, g):
        e = discord.Embed(
            description=f"Usunięto **{g.name}**\nWłaściciel: {g.owner.mention} (**{g.owner.name}**)\nAktualna liczba "
                        f"serwerów: {len(self.bot.guilds)}",
            color=discord.Color.dark_red())
        e.set_author(name="Usunięto serwer", icon_url=g.icon_url)
        await self.bot.get_channel(610827984668065802).send(embed=e)

        await self.bot.clear_settings(g.id)

    @commands.Cog.listener()
    async def on_guild_join(self, g):
        e = discord.Embed(
            description=f"Dodano **{g.name}**\nWłaściciel: {g.owner.mention} (**{g.owner.name}**)\nAktualna liczba "
                        f"serwerów: {len(self.bot.guilds)}",
            color=discord.Color.green())
        e.set_author(name="Dodano serwer", icon_url=g.icon_url)
        await self.bot.get_channel(610827984668065802).send(embed=e)

        guild = await self.bot.db.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", g.id)
        if not guild:
            await self.bot.add_guild_to_database(g.id)

        for channel in g.text_channels:
            try:
                await channel.send(f"{self.bot.english['hey_im']} {self.bot.user.name}. {self.bot.english['ty_for_adding']}")
                break
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.content in ["<@573233127556644873>", "<@573233127556644873> prefix","<@!573233127556644873>",
                               "<@!573233127556644873> prefix"]:
            guild = await self.bot.get_guild_settings(message.guild.id)
            if guild.lang.lower() == "pl":
                msg = f"{self.bot.polish['my_prefix_is']} `{guild.prefix}`"
            elif guild.lang.lower() == "eng":
                msg = f"{self.bot.english['my_prefix_is']} `{guild.prefix}`"
            else:
                # if stuff doesnt work, i found that people usually try mentioning bot to get some info, that's why i added
                # this only here

                raise commands.BadArgument("Language set on this server is wrong.\nPlease join support server to "
                                           "fix this issue.")
            await message.channel.send(msg)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        self.bot.usage[ctx.command.qualified_name] += 1

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1


def setup(bot):
    bot.add_cog(Events(bot))
