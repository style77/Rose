import asyncio
import traceback

import discord
import aiohttp

from .utils import get
from .classes.cache import OnlineStreamsSaver, GuildSettingsCache
from discord.ext import commands, tasks

auth = {"Client-ID": get("twitch_client_id"),
        "Accept": "application/vnd.twitchtv.v5+json"}


class Stream(object):
    def __init__(self, data, *, bot, channel_id, guild_id, lang):
        self.user = data['channel']
        self.channel = None if not bot or not channel_id else bot.get_channel(channel_id)
        self.guild_id = guild_id or None

        self.data = data

        self.embed = None

        self.lang = bot.polish if lang == "PL" else bot.english

    @property
    def is_live(self):
        if self.data is not None:
            return True
        return False

    def _prepare_embed(self):
        if self.is_live:
            text = self.lang['stream_notification'].format(
                                                           self.user['display_name'],
                                                           self.user['display_name'],
                                                           self.user['game'],
                                                           self.user['status']
                                                          )

            self.embed = discord.Embed(description=text, color=0x6441a5)
            self.embed.set_image(url=self.data['preview']['large'])
            self.embed.set_author(name=self.user['display_name'], icon_url=self.data['channel']['logo'])

    async def send_notif(self):
        self._prepare_embed()
        if self.channel and self.embed:
            await self.channel.send(embed=self.embed)

    def __repr__(self):
        return f"Stream(user_id: {self.user}, channel: {self.channel}, guild_id: {self.guild_id}, embed_prepared: " \
               f"{bool(self.embed)}, language: {self.lang})"


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
                streams_fetch = await self.bot.db.fetch("SELECT * FROM twitch_notifications")
                for _stream in streams_fetch:
                    if not _stream:
                        continue
                    async with cs.get(
                            f"https://api.twitch.tv/kraken/users?login={_stream['stream']}", headers=auth) as _id:
                        _id = await _id.json()

                    if 'users' not in _id:
                        continue

                    try:
                        async with cs.get(f"https://api.twitch.tv/kraken/streams/{_id['users'][0]['_id']}",
                                          headers=auth) as stream_ttv:
                            stream_ttv = await stream_ttv.json()
                    except IndexError:
                        continue

                    if stream_ttv['stream'] is None:
                        await online_streams.remove(_stream['guild_id'], _id['users'][0]["_id"])
                        continue

                    get = GuildSettingsCache().get(_stream['guild_id'])
                    if get:
                        notif_channel = get['database']['stream_notification']
                        language = get['database']['lang']
                    else:
                        z = await self.bot.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1",
                                                           _stream['guild_id'])
                        if z:
                            notif_channel = z['stream_notification']
                            language = z['lang']
                        else:
                            continue

                    s = Stream(stream_ttv['stream'], channel_id=notif_channel, bot=self.bot,
                               guild_id=_stream['guild_id'], lang=language)

                    if await online_streams.check(_id['users'][0]['_id'], _stream['guild_id']) is False:
                        await online_streams.add(_stream['guild_id'], _id['users'][0]["_id"])
                        await s.send_notif()
                    else:
                        continue

        except Exception as e:
            traceback.print_exc()

    @twitch_checker.before_loop
    async def twitch_checker_before(self):
        await self.bot.wait_until_ready()

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def stream(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @stream.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, streamer: str = None):
        """Narazie wspiera tylko twitchowych twórców."""
        if not streamer:
            e = discord.Embed(title=ctx.lang['need_to_pass_streamer'], description=ctx.lang['dont_forget_twitch'])
            e.set_image(url="https://i.imgur.com/muVCzNd.png")
            return await ctx.send(embed=e)

        await self.bot.db.execute("INSERT INTO twitch_notifications (stream, guild_id) VALUES ($1, $2)", streamer,
                                      ctx.guild.id)
        await ctx.send(":ok_hand:")

    @stream.command()
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, streamer: str):
        """Usuwa powiadomienia o transmisjach."""
        fetch = await self.bot.db.fetchrow("SELECT * FROM twitch_notifications WHERE stream = $1 AND guild_id = $2",
                                               streamer, ctx.guild.id)
        if not fetch:
            return await ctx.send(ctx.lang['stream_not_set'])
        await self.bot.db.execute("DELETE FROM twitch_notifications WHERE stream = $1 AND guild_id = $2", streamer,
                                      ctx.guild.id)

        online_streams = OnlineStreamsSaver()

        async with aiohttp.ClientSession() as cs:
            async with cs.get(f"https://api.twitch.tv/kraken/users?login={streamer}", headers=auth) as _id:
                _id = await _id.json()

            if 'users' not in _id:
                return await ctx.send(":ok_hand:")

        await online_streams.remove(ctx.guild.id, _id['users'][0]["_id"])

        await ctx.send(":ok_hand:")

    @stream.command()
    async def list(self, ctx):
        streams = await self.bot.db.fetch("SELECT * FROM twitch_notifications WHERE guild_id = $1", ctx.guild.id)

        if not streams:
            return await ctx.send(ctx.lang['no_streams_set'])

        return await ctx.send(f"`{', '.join([s['stream'] for s in streams is s is not None])}`")


def setup(bot):
    bot.add_cog(Streams(bot))
