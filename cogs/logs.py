import discord
from datetime import datetime

from discord.ext import commands, tasks
from cogs.classes import plugin, cache


class Logs(plugin.Plugin):
    def __init__(self, bot):
        self.bot = bot

        # metadata
        self.guild = None
        self.author = None

        self.bot.loop.create_task(self.caching_settings())

    # Cache stuff
    # TODO move this to bot.py

    @tasks.loop(count=1)
    async def caching_settings(self):
        guilds = await self.bot.pg_con.fetch("SELECT * FROM guild_settings")
        for guild in guilds:
            discord_guild = self.bot.get_guild(guild['guild_id'])
            cache.GuildSettingsCache().set(discord_guild, guild)

    @caching_settings.before_loop
    async def caching_settings_before(self):
        # we have to wait until bot is connected, otherwise it wont be possible to fetch
        await self.bot.wait_until_ready()

    @property
    async def channel(self):
        cs = cache.GuildSettingsCache()
        logs_channel = cs[self.guild_id]
        if logs_channel:
            channel = self.bot.get_channel(logs_channel['database']['logs'])
            return channel

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        mod_commands = ['clear']
        if ctx.command.name in mod_commands:
            self.author = ctx.author

    @commands.Cog.listener()
    async def on_message_delete(self, m):
        self.guild = m.guild
        ch = await self.channel

        e = discord.Embed(title=_(get_language(self.bot, self.guild.id), "Wiadomość usunięta"),
                          description=m.content,
                          color=0xb8352c)
        e.set_author(name=m.author, icon_url=m.author.avatar_url)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, m):
        # in bulk_message_delete arg m is list of messages, not one message object or bulk message object
        # that's why we cant get its author and I have to set author after using some of mod commands that are specified
        # in mod_commands.
        # P.S. Im little scared that this will be bugged and people could get people from other server as
        # command authors but we will see.

        self.guild = m.guild
        ch = await self.channel

        e = discord.Embed(title=_(get_language(self.bot, self.guild.id), "Zbiorowe usunięcie wiadomości"),
                          description=_(get_language(self.bot, self.guild.id), "{} wiadomości usuniętych"),
                          color=0x6e100a,
                          timestamp=datetime.timestamp)
        if self.author:
            e.set_author(name=self.author, icon_url=self.author.avatar_url)

        await ch.send(embed=e)


def setup(bot):
    bot.add_cog(Logs(bot))
