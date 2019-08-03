import asyncio
import traceback

import discord
import aiohttp

from cogs.utils import utils
from cogs.classes.cache import OnlineStreamsSaver, GuildSettingsCache
from discord.ext import commands, tasks

auth = {"Client-ID": utils.get_from_config("twitch_client_id"),
        "Accept": "application/vnd.twitchtv.v5+json"}

class Stream(object):
    def __init__(self, data, *, bot, channel_id, guild_id, lang):
        self.user = data['channel']
        self.channel = None if not bot or not channel_id else bot.get_channel(channel_id)
        self.guild_id = guild_id or None

        self.data = data

        self.embed = None

        self.lang = lang or "ENG"

    # def __repr__(self): print(f"<[user_id: {self.user['display_name']}, notifications_channel: {self.channel},
    # guild_id: {self.guild_id}]>")

    @property
    def is_live(self):
        if self.data is not None:
            return True
        return False

    def _prepare_embed(self):
        if self.is_live is False:
            return
        self.embed = discord.Embed(description=_(self.lang, "[{}](https://twitch.tv/{}) rozpoczął transmisje na żywo \
                                                             z {}").format(self.user['display_name'],
                                                                           self.user['display_name'],
                                                                           self.user['game']),
                                   color=0x6441a5)
        self.embed.set_image(url=self.data['preview']['large'])
        self.embed.set_author(name=self.user['display_name'], icon_url=self.data['channel']['logo'])

    async def send_notif(self):
        self._prepare_embed()
        if self.channel and self.embed:
            await self.channel.send(embed=self.embed)

class Streams(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.twitch_checker.start()

    def cog_unload(self):
        self.twitch_checker.cancel()

    @tasks.loop(minutes=2)
    async def twitch_checker(self):
        try:

            online_streams = OnlineStreamsSaver()

            async with aiohttp.ClientSession() as cs:
                streams_fetch = await self.bot.pg_con.fetch("SELECT * FROM twitch_notifications")
                for stream in streams_fetch:
                    _id = await cs.get(f"https://api.twitch.tv/kraken/users?login={stream['stream']}", headers=auth)
                    _id = await _id.json()

                    stream_ttv = await cs.get(f"https://api.twitch.tv/kraken/streams/{_id['users'][0]['_id']}",
                                              headers=auth)
                    stream_ttv = await stream_ttv.json()

                    notif_channel = GuildSettingsCache().get(stream['guild_id'])['database']['stream_notification']
                    language = GuildSettingsCache().get(stream['guild_id'])['database']['lang']

                    if stream_ttv['stream'] is not None:
                        s = Stream(stream_ttv['stream'], channel_id=notif_channel, bot=self.bot,
                                   guild_id=stream['guild_id'], lang=language)

                        try:
                            if int(_id['users'][0]['_id']) not in online_streams.data[stream['guild_id']]['streams_id']:
                                online_streams.add(stream['guild_id'], int(_id['users'][0]["_id"]))
                                await s.send_notif()
                        except KeyError:
                            online_streams.add(stream['guild_id'], int(_id['users'][0]["_id"]))
                            await s.send_notif()
                    else:
                        try:
                            if int(_id['users'][0]['_id']) in online_streams.data[stream['guild_id']]['streams_id']:
                                online_streams.remove(stream['guild_id'], int(_id['users'][0]["_id"]))
                        except KeyError:
                            pass

        except Exception as e:
            traceback.print_exc()

    @twitch_checker.before_loop
    async def twitch_checker_before(self):
        await self.bot.wait_until_ready()

    @commands.group(invoke_without_command=True)
    async def stream(self, ctx):
        z = []
        for cmd in self.bot.get_command("stream").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Komendy w tej grupie:\n```\n{}```").format('\n'.join(z)))

    @stream.command()
    async def add(self, ctx, streamer: str=None):
        """Narazie wspiera tylko twitchowych twórców."""
        if not streamer:
            e = discord.Embed(description=_(ctx.lang, "Nie zapomnij, że zawsze podajemy koncówke z linku."))
            e.set_image(url="https://i.imgur.com/muVCzNd.png")
            await ctx.send(_(ctx.lang, "Podaj kanał z którego powiadomienia będą przychodzić na wyznaczony kanał.\n\
                                       Kanał ustawia się za pomocą komendy `{}set streams #channel`").format(
                                                                                                            ctx.prefix),
                           embed=e)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))
            streamer = msg.content.lower()

        await self.bot.pg_con.execute("INSERT INTO twitch_notifications (stream, guild_id) VALUES ($1, $2)", streamer, ctx.guild.id)
        await ctx.send(":ok_hand:")

    @stream.command()
    async def remove(self, ctx, streamer: str=None):
        """Usuwa powiadomienia o transmisjach."""
        fetch = await self.bot.pg_con.fetchrow("SELECT * FROM twitch_notifications WHERE stream = $1 AND guild_id = $2", streamer, ctx.guild.id)
        if not fetch:
            return await ctx.send(_(ctx.lang, "Ten stream nie jest ustawiony."))
        await self.bot.pg_con.execute("DELTE FROM twitch_notifications WHERE stream = $1 AND guild_id = $2", streamer, ctx.guild.id)
        await ctx.send(":ok_hand:")

    @stream.command()
    async def list(self, ctx):
        streams = await self.bot.pg_con.fetch("SELECT * FROM twitch_notifications WHERE guild_id = $1",
                                               ctx.guild.id)
        if not streams:
            return await ctx.send(_(ctx.lang, "Żadne powiadomienia o transmisjach na żywo nie są ustawione na tym serwerze."))

        return await ctx.send(f"`{', '.join([s['stream'] for s in streams])}`")

def setup(bot):
    bot.add_cog(Streams(bot))
