import asyncio
import itertools
import math
import random
import re
import secrets

import aiohttp
import typing

import inspect

import discord
import humanize
import wavelink
from discord.ext import commands, tasks
from datetime import datetime, timedelta

from .classes.other import Plugin

from .utils import get_language, clean_text
from .utils.misc import get

RURL = re.compile("https?:\/\/(?:www\.)?.+")
SPOTIFY_URI_playlists = re.compile("^(https:\/\/open.spotify.com\/playlist\/|spotify:user:spotify:playlist:)([a-zA-Z0-9]+)(.*)$")
SPOTIFY_URI_tracks = re.compile("^(https:\/\/open.spotify.com\/track\/|spotify:track:)([a-zA-Z0-9]+)(.*)$")
SPOTIFY_URI_albums = re.compile("^(https:\/\/open.spotify.com\/album\/|spotify:track:)([a-zA-Z0-9]+)(.*)$")


class SavedQueue:
    """
    123XYZ: ["https://youtube.com/123", "https://youtube.com/1234"]
    """
    def __init__(self, bot):
        self._tracks = list()
        self.bot = bot

    @classmethod
    async def from_tracks(cls, bot, tracks):
        queue = cls(bot)
        queue._tracks.extend(tracks)
        code = await queue.save()
        return code

    async def save(self):
        code = secrets.token_hex(8)
        for track in self._tracks:
            print(track.uri)
            z = await self.bot.redis.lpush(code, track.uri)
            print(z)
        return code

    @property
    def tracks(self):
        return self._tracks


class Spotify:
    __slots__ = ("_playlist_cache", "_songs_cache", "_albums_cache", "session", "token")

    def __init__(self):
        self._playlist_cache = dict()
        self._songs_cache = dict()
        self._albums_cache = dict()

        self.session = aiohttp.ClientSession()

        self.token = None

    async def _get_token(self):
        if self.token:
            return self.token

        spotify_id = get("spotify_id")
        spotify_secret = get("spotify_secret")

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type': 'client_credentials',
            'client_id': spotify_id,
            'client_secret': spotify_secret
        }

        async with self.session.post('https://accounts.spotify.com/api/token', headers=headers, params=data) as r:
            res = await r.json()

        self.token = token = res['access_token']
        return token

    async def get_from_url(self, url):
        find = SPOTIFY_URI_tracks.findall(url)
        if not find:
            raise commands.BadArgument("This is not correct url.")

        track_id = find[0][1]

        url = f"https://api.spotify.com/v1/tracks/{track_id}"

        token = await self._get_token()

        headers = {'Authorization': f'Bearer {token}'}

        async with self.session.get(url, headers=headers) as r:
            res = await r.json()

        return res

    async def get_playlist_from_url(self, url):
        find = SPOTIFY_URI_playlists.findall(url)
        if not find:
            raise commands.BadArgument("This is not correct url.")

        playlist_id = find[0][1]

        url = f"https://api.spotify.com/v1/playlists/{playlist_id}"

        token = await self._get_token()

        headers = {'Authorization': f'Bearer {token}'}

        async with self.session as cs:
            async with cs.get(url, headers=headers) as r:
                res = await r.json()

        return res

    async def get_album_from_id(self, url):
        find = SPOTIFY_URI_albums.findall(url)
        if not find:
            raise commands.BadArgument("This is not correct url.")

        id_ = find[0][1]

        url = f"https://api.spotify.com/v1/albums/{id_}"

        token = await self._get_token()

        headers = {'Authorization': f'Bearer {token}'}

        async with self.session as cs:
            async with cs.get(url, headers=headers) as r:
                res = await r.json()

        print(res)

        return res


class Track(wavelink.Track):
    __slots__ = ('requester', 'channel', 'message', 'looped')

    def __init__(self, id_, info, *, ctx=None):
        super(Track, self).__init__(id_, info)

        self.requester = ctx.author
        self.channel = ctx.channel
        self.message = ctx.message

    @property
    def is_dead(self):
        return self.dead


class MusicController:
    __slots__ = ('ctx', 'message', 'player', '_embed', 'reactions', 'controls', 'reactions_task', 'controller', 'updater', 'controller_task', 'bot')
    
    def __init__(self, bot, context, player):
        self.bot = bot
        
        self.message = None
        self.ctx = context
        self.player = player
        self._embed = None
        
        self.controls = {'⏯': 'rp',
                         '⏹': 'stop',
                         '⏭': 'skip',
                         '🔀': 'shuffle',
                         '🔁': 'queue_loop',
                         '🔂': 'loop',
                         '➕': 'vol_up',
                         '➖': 'vol_down',
                         'ℹ': 'queue',
                         '❌': 'finish_mc'}
        
        self.updater = bot.loop.create_task(self.updater_())

    async def updater_(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            if self.message:
                if not await self.is_current_fresh():
                    await self.resend()

            await asyncio.sleep(10)

    async def invoke_react(self, cmd):
        if not cmd._buckets.valid:
            return True

        if not (await cmd.can_run(self.ctx)):
            return False

        bucket = cmd._buckets.get_bucket(self.ctx)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return False
        return True

    async def destroy_controller(self):
        try:
            await self.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass
        
        self.player.reaction_controller.cancel()
        self.message = None
                
    async def is_current_fresh(self):
        """Check whether our controller is fresh in message history."""
        try:
            async for m in self.message.channel.history(limit=8):
                if m.id == self.message.id:
                    return True
        except (discord.HTTPException, AttributeError):
            return False
        return False

    async def invoke(self):
        self.message = await self.ctx.send(embed=self.embed)
        if not self.player.controller_task:
            self.player.controller_task = self.bot.loop.create_task(self.player.reaction_controller())

    async def resend(self):
        if self.message:
            try:
                await self.message.delete()
            except (discord.HTTPException, discord.Forbidden):
                return await self.ctx.send(self.ctx.lang['cant_resend_mc'])
        
        self.message = await self.ctx.send(embed=self.embed)
        if not self.player.controller_task:
            self.player.controller_task = self.bot.loop.create_task(self.player.reaction_controller())

    @property
    def embed(self):
        self._embed = self._prepare_embed()
        return self._embed

    def _prepare_embed(self):
        if not self.player.current:
            addon = ""
        elif self.player.current.is_stream:
            addon = "🔴 LIVE"
        elif self.player.repeat:
            addon = "🔂"
        elif self.player.queue_loop:
            addon = "🔁"
        else:
            addon = ""
        
        e = discord.Embed(color=self.bot.color)
        
        if self.player.current:
            fmt = f"""\n
            **[{self.player.current.title}]({self.player.current.uri}) {addon}**
            
            **VOLUME**: `{self.player.volume}%`
            **INFO CHANNEL**: `{self.player.text_channel.name}`
            **CURRENT DJ**: {self.player.dj.mention if self.player.dj else '`no one`'}
            **QUEUE LENGHT**: `{str(len(self.player.entries))}`
            """
            e.set_thumbnail(url=self.player.current.thumb)
        
        else:
            fmt = "**NOTHING**"
        
        e.description = fmt
        
        return e

    async def do(self, command: str, *args, **kwargs):
        func = getattr(self, f'cmd_{command}')
        if inspect.iscoroutine(func):
            return await func(args, **kwargs)
        return func(args, **kwargs)

    # commands
    
    async def cmd_change_info_channel(self, channel=None):
        channel = channel or self.ctx.channel
        self.player.text_channel = channel
        
        await self.ctx.send(self.ctx.lang['new_music_info_channel'].format(channel.name))


class Player(wavelink.Player):
    def __init__(self, bot: typing.Union[commands.Bot, commands.AutoShardedBot], guild_id: int, node: wavelink.Node):
        super(Player, self).__init__(bot, guild_id, node)

        self.bot = bot

        self.queue = asyncio.Queue(loop=self.bot.loop)
        self.next_event = asyncio.Event()

        self.volume = 80
        self.dj = None
        self.eq = 'Flat'

        self._save_queue = False
        self.queue_loop = False
        self.repeat = None
        self.text_channel = None
        self.last_play_info = None

        self.last_track = None

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()

        self.inactive = True
        
        self.music_controller = None

        bot.loop.create_task(self.player_loop())
        self.reaction_task = None
        self.controller_task = None

    async def add_reactions(self):
        for reaction in self.music_controller.controls.keys():
            try:
                await self.music_controller.message.add_reaction(str(reaction))
            except discord.HTTPException:
                pass

    async def reaction_controller(self):
        print('b44')
        self.bot.loop.create_task(self.add_reactions())
        print('d')
        
        def check(r, u):
            if u.id == 185712375628824577:
                return True
        
        while self.music_controller.message:
            print('b4')
            
            react, user = await self.bot.wait_for('reaction_add', check=check)
            
            print('after')
            print(react, user)
            
            control = self.music_controller.controls.get(str(react))

            print(control)

            if control == 'finish_mc':
                await self.music_controller.destroy_controller()

            if control == 'rp':
                if self.current.pause:
                    control = 'resume'
                else:
                    control = 'pause'
                
            try:
                await self.music_controller.message.remove_reaction(react, user)
            except discord.HTTPException:
                pass
            
            cmd = self.bot.get_command(control)

            ctx = await self.bot.get_context(react.message)
            ctx.author = user

            try:
                if cmd.is_on_cooldown(ctx):
                    pass
                if not await self.music_controller.invoke_react(cmd):
                    pass
                else:
                    self.bot.loop.create_task(ctx.invoke(cmd))
            except Exception as e:
                print(e)
                #ctx.command = self.bot.get_command('reactcontrol')
                #await cmd.dispatch_error(ctx=ctx, error=e)
        await self.music_controller.destroy_controller()

    @property
    def entries(self):
        return list(self.queue._queue)

    async def create_music_controller(self, ctx):
        mc = self.music_controller = MusicController(self.bot, ctx, self)
        await mc.invoke()

    async def player_loop(self):
        await self.bot.wait_until_ready()

        await self.set_preq('Flat')

        await self.set_volume(self.volume)

        language = await get_language(self.bot, self.guild_id)
        lang = self.bot.get_language_object(language)

        while not self.bot.is_closed():
            self.next_event.clear()

            self.inactive = False

            self.paused = False

            if self.repeat:
                track = self.repeat

            elif self.current and len(self.entries) == 0:
                track = None

                await self.text_channel.send(lang['queue_ended'])

            elif self.queue_loop:
                track = await self.queue.get()
                await self.queue.put(track)
            else:
                track = await self.queue.get()
            self.current = track

            if track is not None:
                await self.play(track)

                if not self.repeat:

                    if self.last_play_info:
                        try:
                            await self.last_play_info.delete()
                        except (discord.HTTPException, discord.Forbidden):
                            pass

                    if self.text_channel:
                        self.last_play_info = await self.text_channel.send(lang['playing_now'].format(
                            clean_text(self.current.title)))
                    self.pauses.clear()
                    self.resumes.clear()
                    self.stops.clear()
                    self.shuffles.clear()
                    self.skips.clear()
                    self.repeats.clear()

                await self.next_event.wait()


class Music(Plugin):
    def __init__(self, bot):
        super().__init__(bot)

        self.bot = bot
        self.spotify = Spotify()

        self.nodes = self.bot.loop.create_task(self.initiate_nodes())
        self.leave_channels.start()

    def cog_unload(self):
        self.leave_channels.cancel()
        self.nodes.cancel()

    async def initiate_nodes(self):
        nodes = {'MAIN': {'host': '127.0.0.1',
                          'port': 1334,
                          'rest_url': 'http://127.0.0.1:1334',
                          'password': "youshallnotpass",
                          'identifier': 'style',
                          'region': 'eu_central'}}

        for n in nodes.values():
            node = await self.bot.wavelink.initiate_node(host=n['host'],
                                                         port=n['port'],
                                                         rest_uri=n['rest_url'],
                                                         password=n['password'],
                                                         identifier=n['identifier'],
                                                         region=n['region'],
                                                         secure=False)

            node.set_hook(self.event_hook)

    @tasks.loop(minutes=5)
    async def leave_channels(self):
        try:
            for guild_id, player in self.bot.wavelink.players.items():

                guild = self.bot.get_guild(guild_id)

                if not guild:
                    continue

                vc = guild.me.voice

                if not vc:
                    continue

                if len(vc.channel.members) == 1:
                    print('ye')
                    player.queue._queue.clear()
                    await player.disconnect()
                else:
                    print('no')
        except Exception as e:
            print(e)

    @leave_channels.before_loop
    async def before_leave_channels(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def event_hook(event):
        if isinstance(event, wavelink.TrackEnd):
            event.player.next_event.set()
        elif isinstance(event, wavelink.TrackException):
            print(event.error)

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        else:
            return True

    def required(self, player, invoked_with):
        channel = self.bot.get_channel(int(player.channel_id))
        if invoked_with == 'stop':
            if len(channel.members) - 1 == 2:
                return 2

        return math.ceil((len(channel.members) - 1) / 2.5)

    async def has_perms(self, ctx, **perms):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if player.dj:
            if ctx.author.id == player.dj.id:
                return True

        role = discord.utils.get(ctx.guild.roles, name="dj")
        if role in ctx.author.roles:
            return True

        ch = ctx.channel
        permissions = ch.permissions_for(ctx.author)

        missing = [perm for perm, value in perms.items(
        ) if getattr(permissions, perm, None) != value]

        if not missing:
            return True

        return False

    async def vote_check(self, ctx, command: str):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        vcc = len(self.bot.get_channel(int(player.channel_id)).members) - 1
        votes = getattr(player, command + 's', None)

        if vcc < 3 and not ctx.invoked_with == 'stop':
            votes.clear()
            return True
        else:
            votes.add(ctx.author.id)

            if len(votes) >= self.required(player, ctx.invoked_with):
                votes.clear()
                return True
        return False

    async def do_vote(self, ctx, player, command: str):
        attr = getattr(player, command + 's', None)
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.author.id in attr:
            await ctx.send(ctx.lang['already_voted'].format(ctx.author.mention))
        elif await self.vote_check(ctx, command):
            await ctx.send(ctx.lang['outvoted'].format(command))
            to_do = getattr(self, f'do_{command}')
            await to_do(ctx)
        else:
            await ctx.send(ctx.lang['voted_on'].format(ctx.author.mention, command,
                                                       self.required(player, ctx.invoked_with) - len(attr)))

    async def connect_handler(self, ctx, msg):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if ctx.guild.me.voice:
            if ctx.guild.me.voice.channel == ctx.author.voice.channel:
                await msg.edit(content=ctx.lang['am_already_connected'])
                return None
        try:
            await ctx.guild.me.move_to(ctx.author.voice.channel)
            return True
        except:
            try:
                await player.connect(ctx.author.voice.channel.id)
                return True
            except:
                return False

    @commands.command(aliases=['join'])
    async def connect(self, ctx):
        if not ctx.author.voice:
            return await ctx.send(ctx.lang['you_arent_on_any_vc'])

        msg = await ctx.send(ctx.lang['connecting_to_vc'].format(ctx.author.voice.channel.name))

        x = await self.connect_handler(ctx, msg)

        try:
            await ctx.guild.me.edit(deafen=True)
        except discord.HTTPException:
            pass

        if x:
            return await msg.edit(content=ctx.lang['connected_to_vc'].format(ctx.author.voice.channel.name))
        else:
            return await msg.edit(content=ctx.lang['error_while_connecting_to_vc'])

    @commands.command(aliases=['dc', 'stop'])
    async def disconnect(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return print('s')

        await player.disconnect()
        await player.stop()
        player.queue._queue.clear()

        player.current = None

        await ctx.send(ctx.lang['disconnected'])

    @commands.command(aliases=['play_saved_queue', 'psq'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play_from_queue(self, ctx, *, code: str):
        async with ctx.typing():

            player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

            if not player.is_connected or not ctx.guild.me.voice:
                await ctx.invoke(self.connect)

            if (ctx.guild.me.voice and ctx.author.voice) and ctx.guild.me.voice.channel != ctx.author.voice.channel:
                await ctx.invoke(self.connect)

            warn_msg = None

            if not ctx.author.voice:
                warn_msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])

            elif not ctx.guild.me.voice:
                warn_msg = await ctx.send(ctx.lang['am_not_on_any_vc'])

            elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
                warn_msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])

            if warn_msg:
                if (player.is_connected or ctx.guild.me.voice) and ctx.author.voice and \
                        ctx.guild.me.voice.channel == ctx.author.voice.channel:
                    try:
                        await warn_msg.delete()
                    except discord.HTTPException:
                        return
                else:
                    return

            if not player.dj:
                player.dj = ctx.author

            queue = await self.bot.redis.lrange(code, 0, -1)

            if not queue:
                await ctx.send(ctx.lang['queue_not_found'].format(code))

            tracks = list()
            for query in queue:
                track = await self.bot.wavelink.get_tracks(query.decode('utf-8').replace('<', '').replace('>', ''))
                if not track:
                    continue
                tracks.append(track[0])

            for t in tracks:
                print(tracks)
                print(t)
                await player.queue.put(Track(t.id, t.info, ctx=ctx))

            if not player.entries:
                current = player.current = queue[0]
                player.last_track = player.entries.index(player.current)
                # return await ctx.send(ctx.lang['playing_now'].format(current))
            else:
                return await ctx.send(ctx.lang['added_to_queue_from_code'].format(code))

    @commands.command(aliases=['p', '>'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play(self, ctx, *, query: str):
        async with ctx.typing():

            orginal_query = query = query.strip('<>')

            player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

            if not player.is_connected or not ctx.guild.me.voice:
                await ctx.invoke(self.connect)
                
            if (ctx.guild.me.voice and ctx.author.voice) and ctx.guild.me.voice.channel != ctx.author.voice.channel:
                await ctx.invoke(self.connect)

            warn_msg = None

            if not ctx.author.voice:
                warn_msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])

            elif not ctx.guild.me.voice:
                warn_msg = await ctx.send(ctx.lang['am_not_on_any_vc'])
            
            elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
                warn_msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])
                
            if warn_msg:
                if (player.is_connected or ctx.guild.me.voice) and ctx.author.voice and \
                        ctx.guild.me.voice.channel == ctx.author.voice.channel:
                    try:
                        await warn_msg.delete()
                    except discord.HTTPException:
                        return
                else:
                    return

            if not player.dj:
                player.dj = ctx.author

            if SPOTIFY_URI_tracks.match(query):
                res = await self.spotify.get_from_url(query)
                artists = []
                i = 0
                for _ in res['artists']:
                    artists.append(res['artists'][i]['name'])
                query = f"{' '.join(artists)} {res['name']}"
                tracks = await self.bot.wavelink.get_tracks(f"ytsearch:{query}")

            elif SPOTIFY_URI_albums.match(query):
                if query in self.spotify._albums_cache:
                    raw_data = self.spotify._albums_cache.get(query)
                    tracks = raw_data['tracks']
                    res = raw_data['data']

                    for t in tracks:
                        await player.queue.put(t)

                    if not player.entries:
                        player.current = tracks[0]

                else:
                    res = await self.spotify.get_album_from_id(query)

                    tracks = []

                    for track in res['tracks']['items']:
                        artists = []

                        for artist in track['artists']:
                            artists.append(artist['name'])

                        query = f"{' '.join(artists)} - {track['name']}"
                        track_ = await self.bot.wavelink.get_tracks(f"ytsearch: {query}")

                        if not track_:
                            continue

                        if track_[0] not in tracks:
                            tracks.append(track_[0])

                    for t in tracks:
                        await player.queue.put(Track(t.id, t.info, ctx=ctx))

                    if not player.entries:
                        player.current = tracks[0]

                    self.spotify._albums_cache[orginal_query] = {}
                    self.spotify._albums_cache[orginal_query]['tracks'] = tracks
                    self.spotify._albums_cache[orginal_query]['data'] = res

                return await ctx.send(ctx.lang['added_album_to_queue'].format(res['name'], len(tracks)))

            elif SPOTIFY_URI_playlists.match(query):
                if query in self.spotify._playlist_cache:
                    raw_data = self.spotify._playlist_cache.get(query)
                    tracks = raw_data['tracks']
                    res = raw_data['data']

                    for t in tracks:
                        await player.queue.put(t)

                    if not player.entries:
                        player.current = tracks[0]

                else:
                    res = await self.spotify.get_playlist_from_url(query)

                    tracks = []

                    for track in res['tracks']['items']:
                        artists = []

                        for artist in track['track']['artists']:
                            artists.append(artist['name'])

                        query = f"{' '.join(artists)} - {track['track']['name']}"
                        track_ = await self.bot.wavelink.get_tracks(f"ytsearch: {query}")

                        if not track_:
                            continue

                        if track_[0] not in tracks:
                            tracks.append(track_[0])

                    for t in tracks:
                        await player.queue.put(Track(t.id, t.info, ctx=ctx))

                    if not player.entries:
                        player.current = tracks[0]

                    self.spotify._playlist_cache[orginal_query] = {}
                    self.spotify._playlist_cache[orginal_query]['tracks'] = tracks
                    self.spotify._playlist_cache[orginal_query]['data'] = res

                return await ctx.send(ctx.lang['added_playlist_to_queue'].format(res['name'], len(tracks)))

            else:
                tracks = await self.bot.wavelink.get_tracks(f"ytsearch: {query}")

            tracks = await self.bot.wavelink.get_tracks(query) if tracks is None else tracks

            if not tracks:
                return await ctx.send(ctx.lang['song_not_found'])

            if isinstance(tracks, wavelink.TrackPlaylist):
                for t in tracks.tracks:
                    await player.queue.put(Track(t.id, t.info, ctx=ctx))

                await ctx.send(ctx.lang['added_playlist_to_queue'].format(tracks.data["playlistInfo"]["name"],
                                                                          len(tracks.tracks)))
            else:
                track = tracks[0]
                await ctx.send(ctx.lang['added_to_queue'].format(clean_text(track.title)))
                await player.queue.put(Track(track.id, track.info, ctx=ctx))
                if not player.entries:
                    player.current = track
                    player.last_track = player.entries.index(player.current)

    @play.before_invoke
    async def before_play(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        player.text_channel = ctx.channel

    @commands.command(aliases=['np'])
    async def now_playing(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if not player:
            return

        if not player.current:
            return await ctx.send(ctx.lang['nothing_plays'])

        lenght = round(player.current.length / 1000)
        pos = round(player.position / 1000)
        line = lambda p: ''.join(map(lambda x: x[1] if x[0] != round(p * len([*enumerate("─" * 22)])) else '●', [*enumerate("─" * 22)]))
        thing = line(pos / lenght)

        pos = timedelta(seconds=pos)
        lenght = timedelta(seconds=lenght)

        repeat = "" if not player.repeat else "🔂"
        text = \
        f"""\n
        `{clean_text(player.current.title)} {repeat}`
{pos} {thing} {lenght}
        """

        await ctx.send(text)

        # await ctx.send(
        #     _(ctx.lang, "Teraz gra: `{}`." + f" {'🔂' if player.repeat else ''}").format(player.current.title))

    @commands.command(name='pause')
    async def pause_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if not player:
            return

        if player.paused:
            return await ctx.invoke(self.resume_)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(ctx.lang['stopped_song'].format(ctx.author.mention))
            return await self.do_pause(ctx)

        await self.do_vote(ctx, player, 'pause')

    async def do_pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        player.paused = True
        await player.set_pause(True)

    @commands.command(name='resume')
    async def resume_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if not player:
            return

        if not player.paused:
            return await ctx.invoke(self.pause_)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(ctx.lang['resumed_song'].format(ctx.author.mention))
            return await self.do_resume(ctx)

        await self.do_vote(ctx, player, 'resume')

    async def do_resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.set_pause(False)

    @commands.command(name='skip')
    @commands.cooldown(5, 10, commands.BucketType.user)
    async def skip_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if (len(player.entries) + 1 if player.current else 0) == 0:
            return await ctx.send(ctx.lang['no_more_songs_to_skip'])

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(ctx.lang['skipped_song'].format(ctx.author.mention))
            return await self.do_skip(ctx)

        await self.do_vote(ctx, player, 'skip')

    async def do_skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        await player.stop()
        player.repeat = False

    @commands.command(name='equalizer', aliases=['eq', 'seteq', 'set_eq'])
    async def set_eq(self, ctx, *, eq: str):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if eq.upper() not in player.equalizers:
            return await ctx.send(ctx.lang['not_correct_eq'].format(eq))

        await player.set_preq(eq)
        player.eq = eq.capitalize()
        await ctx.send(ctx.lang['eq_set'].format(eq.capitalize()))

    @commands.command(aliases=['vol'])
    @commands.cooldown(1, 2, commands.BucketType.guild)
    async def volume(self, ctx, *, value: int):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if not 0 < value < 101:
            return await ctx.send(ctx.lang['pass_value_from_0_100'])

        if not await self.has_perms(ctx, manage_guild=True) and player.dj.id != ctx.author.id:
            if (len(ctx.guild.me.voice.channel.members) - 1) > 2:
                return await ctx.send(ctx.lang['too_many_people_to_change_vol'])

        await player.set_volume(value)
        await ctx.send(ctx.lang['set_volume_to'].format(value))

    @commands.command(aliases=['s_q', 'save_que', 's_queue'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def save_queue(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            print('sr')
            return

        if not player.entries:
            return await ctx.send(ctx.lang['nothing_in_queue'])

        code = await SavedQueue.from_tracks(self.bot, player.entries)
        await ctx.send(ctx.lang['saved_queue'].format(code))

    @commands.command(name='queue', aliases=['q', 'que'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def queue_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if not player.entries:
            return await ctx.send(ctx.lang['nothing_in_queue'])

        entries = [f'`{str(song)}`' for song in player.entries]

        await ctx.paginate(entries=entries, colour=3553598, author=ctx.author, title=f"{ctx.lang['now_playing']}: {player.current}")

    @commands.command(name='shuffle', aliases=['mix'])
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def shuffle_(self, ctx):
        """Miesza piosenki w kolejce."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if len(player.entries) < 3:
            return await ctx.send(ctx.lang['too_few_songs'])

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(ctx.lang['on_vc_shuffle'].format(ctx.author.mention))
            return await self.do_shuffle(ctx)

        await self.do_vote(ctx, player, 'shuffle')

    async def do_shuffle(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
        random.shuffle(player.queue._queue)

        player.update = True

    @commands.command(name='repeat', aliases=['l', 'loop'])
    async def repeat_(self, ctx):
        """Włącza powtarzanie aktualnej piosenki."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        if await self.has_perms(ctx, manage_guild=True):
            if player.repeat:
                text = ctx.lang['off_vc_song']

            else:
                text = ctx.lang['on_vc_song']

            await ctx.send(text.format(ctx.author.mention))
            return await self.do_repeat(ctx)

        await self.do_vote(ctx, player, 'repeat')

    async def do_repeat(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if player.repeat:
            player.repeat = None
        else:
            player.repeat = player.current

        player.update = True

    @commands.command()
    async def seek(self, ctx, position: int):
        """Włącza powtarzanie aktualnej piosenki."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        orginal_position = position
        position = position * 1000

        await self.connection_check(ctx)

        if await self.has_perms(ctx, manage_guild=True):
            await ctx.send(ctx.lang['seeked'].format(ctx.author.mention, orginal_position))
            return await self.do_seek(ctx, position)

        # await self.do_vote(ctx, player, 'seek')

    async def do_seek(self, ctx, position):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await player.seek(position)

    # @commands.command(enabled=False)
    # @commands.cooldown(1, 10, commands.BucketType.guild)
    # async def save_queue(self, ctx):
    #     """Zapisuje pozostałe piosenki z playlisty na następne włączenie muzyki."""
    #     player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
    #
    #     if not await self.has_perms(ctx, manage_guild=True):
    #         return await ctx.send(_(ctx.lang, "Nie masz odpowiednich uprawnień do zapisania kolejki."))
    #
    #     # player and member instances check
    #     if not ctx.author.voice:
    #         await ctx.send(_(ctx.lang, "Nie jesteś ze mną na kanale."))
    #         return await add_react(ctx.message, False)
    #
    #     elif not ctx.guild.me.voice:
    #         await ctx.send(_(ctx.lang, "Nie jestem na żadnym kanale."))
    #         return await add_react(ctx.message, False)
    #
    #     elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
    #         await ctx.send(_(ctx.lang, "Nie jesteś ze mną na kanale."))
    #         return await add_react(ctx.message, False)
    #
    #     c = player._save_queue = not player._save_queue
    #
    #     if c is True:
    #         return await ctx.send(_(ctx.lang, "{} włączył zapisywanie playlisty.").format(ctx.author.mention))
    #     else:
    #         return await ctx.send(_(ctx.lang, "{} wyłączył zapisywanie playlisty.").format(ctx.author.mention))

    @commands.command(aliases=['loop_queue', 'lq'])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def queue_loop(self, ctx):
        """Włącza powtarzanie kolejki."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        ch = await self.connection_check(ctx)
        if not ch:
            return

        c = player.queue_loop = not player.queue_loop

        if c is True:
            return await ctx.send(ctx.lang['on_vc_loop'].format(ctx.author.mention))
        else:
            return await ctx.send(ctx.lang['off_vc_loop'].format(ctx.author.mention))

    @commands.command(hidden=True, aliases=['minfo'])
    @commands.is_owner()
    async def music_info(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        node = player.node

        used = humanize.naturalsize(node.stats.memory_used)
        total = humanize.naturalsize(node.stats.memory_allocated)
        free = humanize.naturalsize(node.stats.memory_free)
        cpu = node.stats.cpu_cores

        fmt = f'**WaveLink:** `{wavelink.__version__}`\n\n' \
              f'Connected to `{len(self.bot.wavelink.nodes)}` nodes.\n' \
              f'Best available Node `{self.bot.wavelink.get_best_node().__repr__()}`\n' \
              f'`{len(self.bot.wavelink.players)}` players are distributed on nodes.\n' \
              f'`{node.stats.players}` players are distributed on server.\n' \
              f'`{node.stats.playing_players}` players are playing on server.\n\n' \
              f'Server Memory: `{used}/{total}` | `({free} free)`\n' \
              f'Server CPU: `{cpu}`\n\n' \
              f'Server Uptime: `{timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)

    async def connection_check(self, ctx):
        # player and member instances check
        if not ctx.author.voice:
            print('1')
            msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])
            return False

        elif not ctx.guild.me.voice:
            print('2')
            msg = await ctx.send(ctx.lang['am_not_on_any_vc'])
            return False
        
        elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
            print('3')
            msg = await ctx.send(ctx.lang['arent_with_me_on_vc'])
            return False
        else:
            return True

    @commands.group(enabled=False, name='mc', aliases=['music_controller', 'controller', 'invoke_controller'])
    async def mc_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await self.connection_check(ctx)

        if not player:
            return

        if player.music_controller:
            await player.music_controller.resend()
            
        else:
            await player.create_music_controller(ctx)
            
    @mc_.command(enabled=False)
    async def change_info_channel(self, ctx, channel=None):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        await self.connection_check(ctx)

        if not player:
            return
        
        channel = channel or ctx.channel
        await player.music_controller.do('change_info_channel')

def setup(bot):
    bot.add_cog(Music(bot))
