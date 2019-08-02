import discord
import aiohttp

from cogs.utils import utils
from cogs.classes.cache import OnlineStreamsSaver, GuildSettingsCache
from discord.ext import commands, tasks

auth = {"Client-ID": utils.get_from_config("twitch_client_id"),
        "Accept": "application/vnd.twitchtv.v5+json"}


class Stream(object):
    def __init__(self, data, *, bot, channel_id, guild_id):
        self.user = data['channel']
        self.channel = None if not bot or not channel_id else bot.get_channel(channel_id)
        self.guild_id = guild_id or None

        self.data = data
        print(self.data)

        self.embed = None

    # def __repr__(self):
    #     print(f"<[user_id: {self.user['display_name']}, notifications_channel: {self.channel}, guild_id: {self.guild_id}]>")

    @property
    async def is_live(self):
        if self.data is not None:
            return True
        return False

    def _prepare_embed(self):
        if self.live is False:
            return
        self.embed = discord.Embed(description=f"[{self.user['display_name']} rozpoczął transmisje na żywo z {self.data['game']}](https://twitch.tv/{self.user['display_name']})", color=0x910ec4)

    async def send_notif(self):
        await self.prepare_embed()
        if self.channel and self.embed:
            await self.channel.send(self.embed)


class Streams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_checker.start()

    @tasks.loop(minutes=2)
    async def twitch_checker(self):

        online_streams = OnlineStreamsSaver()

        async with aiohttp.ClientSession() as cs:
            streams_fetch = await self.bot.pg_con.fetch("SELECT * FROM twitch_notifications")
            for stream in streams_fetch:

                _id = await cs.get(f"https://api.twitch.tv/kraken/users?login={stream['stream']}", headers=auth)
                _id = await _id.json()

                stream = await cs.get(f"https://api.twitch.tv/kraken/streams/?channel={_id['_id']}", headers=auth)
                stream = await stream.json()

                notif_channel = GuildSettingsCache.get(stream['guild_id'])['stream_notification']

                s = Stream(stream['stream'], channel_id=notif_channel, bot=self.bot, guild_id=stream['guild_id'])
                if str(stream["_id"]) not in online_streams.data:
                    online_streams.add(stream['guild_id'], str(stream["_id"]))
                    await s.send_notif()

def setup(bot):
    bot.add_cog(Streams(bot))