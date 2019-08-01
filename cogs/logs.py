import discord

from cogs.classes.plugin import Plugin

class Logs(Plugin):
    def __init__(self, bot):
        self.bot = bot
        self.guild_id = None

    @property
    async def channel(self):
        logs_channel = await self.bot.pg_con.fetchrow("SELECT logs from guild_settings WHERE guild_id = $1",
                                                      self.guild_id)
        channel = self.bot.get_channel(logs_channel[0])
        return channel

    @commands.Cog.listener()
    async def on_message_delete(self, m):
        self.guild_id = m.guild.id
        ch = await self.channel

        e = discord.Embed(title=_(get_language(self.bot, self.guild_id), "Wiadomość usunięta"), color=0xb8352c)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, m):
        # in bulk_message_delete arg m is *list* of messages not one message object or bulk message object
        self.guild_id = m.guild.id
        ch = await self.channel

        e = discord.Embed(title=_(get_language(self.bot, self.guild_id), "Zbiorowe usunięcie wiadomości"),
                          color=0x6e100a)

        await ch.send(embed=e)

def setup(bot):
    bot.add_cog(Logs(bot))
