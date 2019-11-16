import asyncio
import itertools
import math
import random
import re

import aiohttp
import typing

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


class Spotify:
    def __init__(self):
        self._playlist_cache = dict()
        self._songs_cache = dict()

    async def _get_token(self):
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

        async with aiohttp.ClientSession() as cs:
            async with cs.post('https://accounts.spotify.com/api/token', headers=headers, params=data) as r:
                res = await r.json()

        token = res['access_token']
        return token

    async def get_from_url(self, url):
        find = SPOTIFY_URI_tracks.findall(url)
        if not find:
            raise commands.BadArgument("This is not correct url.")

        track_id = find[0][1]

        url = f"https://api.spotify.com/v1/tracks/{track_id}"

        token = await self._get_token()

        headers = {'Authorization': f'Bearer {token}'}

        async with aiohttp.ClientSession() as cs:
            async with cs.get(url, headers=headers) as r:
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

        async with aiohttp.ClientSession() as cs:
            async with cs.get(url, headers=headers) as r:
                res = await r.json()

        return res

    def add_to_cache(self, query, track: wavelink.Track):
        if track not in self._music_cache:
            self._music_cache.append(track)


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


class Player(wavelink.Player):

    def __init__(self, bot: typing.Union[commands.Bot, commands.AutoShardedBot], guild_id: int, node: wavelink.Node):
        super(Player, self).__init__(bot, guild_id, node)

        self.queue = asyncio.Queue()
        self.next_event = asyncio.Event()

        self.volume = 80
        self.dj = None
        self.eq = 'Flat'

        self._save_queue = False
        self.queue_loop = False
        self.repeat = None
        self.text_channel = None

        self.last_track = None

        self.pauses = set()
        self.resumes = set()
        self.stops = set()
        self.shuffles = set()
        self.skips = set()
        self.repeats = set()

        self.inactive = True

        bot.loop.create_task(self.player_loop())

    @property
    def entries(self):
        return list(self.queue._queue)

    async def player_loop(self):
        await self.bot.wait_until_ready()

        await self.set_preq('Flat')

        await self.set_volume(self.volume)

        language = await get_language(self.bot, self.guild_id, only_id=True)
        lang = self.bot.polish if language == "PL" else self.bot.english

        while True:
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

                    await self.text_channel.send(lang['playing_now'].format(clean_text(self.current.title)))
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

    @tasks.loop(minutes=10)
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
                    await player.disconnect()
                    player.queue._queue.clear()
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
        except Exception:
            try:
                await player.connect(ctx.author.voice.channel.id)
                return True
            except Exception:
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

        await player.disconnect()
        await player.stop()
        player.queue._queue.clear()

        player.current = None

        await ctx.send(ctx.lang['disconnected'])

    @commands.command(aliases=['p', '>'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def play(self, ctx, *, query: str):
        async with ctx.typing():

            orginal_query = query = query.strip('<>')

            player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

            if not player.is_connected or not ctx.guild.me.voice:
                await ctx.invoke(self.connect)

            # player and member instances check
            if not ctx.author.voice:
                return await ctx.send(ctx.lang['arent_with_me_on_vc'])

            elif not ctx.guild.me.voice:
                return await ctx.send(ctx.lang['am_not_on_any_vc'])

            elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
                return await ctx.send(ctx.lang['arent_with_me_on_vc'])

            # if hasattr(player, 'dj'):
            if not player.dj:
                player.dj = ctx.author
            # else:
            #     owner = ctx.bot.get_user(ctx.bot.owner_id)
            #     await owner.send(
            #         f"For some reasons player object does not have dj attr, you have to restart bot.")

            if SPOTIFY_URI_tracks.match(query):
                res = await self.spotify.get_from_url(query)
                artists = []
                i = 0
                for _ in res['artists']:
                    artists.append(res['artists'][i]['name'])
                query = f"{' '.join(artists)} {res['name']}"
                tracks = await self.bot.wavelink.get_tracks(f"ytsearch:{query}")

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
        if not player:
            return

        if not player.current:
            return await ctx.send(ctx.lang['nothing_plays'])

        lenght = round(player.current.length / 1000)
        pos = round(player.position / 1000)
        line = lambda p: ''.join(map(lambda x: x[1] if x[0] != round(p * len([*enumerate("─" * 25)])) else '●', [*enumerate("─" * 25)]))
        thing = line(pos / lenght)

        pos = timedelta(seconds=pos)
        lenght = timedelta(seconds=lenght)

        text = f"""\n
      `{clean_text(player.current.title)}`
{pos} {thing} {lenght}
        """

        await ctx.send(text)

        # await ctx.send(
        #     _(ctx.lang, "Teraz gra: `{}`." + f" {'🔂' if player.repeat else ''}").format(player.current.title))

    @commands.command(name='pause')
    async def pause_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)
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

        if eq.upper() not in player.equalizers:
            return await ctx.send(ctx.lang['not_correct_eq'].format(eq))

        await player.set_preq(eq)
        player.eq = eq.capitalize()
        await ctx.send(ctx.lang['eq_set'].format(eq.capitalize()))

    @commands.command(aliases=['vol'])
    @commands.cooldown(1, 2, commands.BucketType.guild)
    async def volume(self, ctx, *, value: int):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        if not 0 < value < 101:
            return await ctx.send(ctx.lang['pass_value_from_0_100'])

        if not await self.has_perms(ctx, manage_guild=True) and player.dj.id != ctx.author.id:
            if (len(ctx.guild.me.voice.channel.members) - 1) > 2:
                return await ctx.send(ctx.lang['too_many_people_to_change_vol'])

        await player.set_volume(value)
        await ctx.send(ctx.lang['set_volume_to'].format(value))

    @commands.command(name='queue', aliases=['q', 'que'])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def queue_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

        upcoming = list(itertools.islice(player.entries, 0, 10))

        if not player.entries or not upcoming:
            return await ctx.send(ctx.lang['nothing_in_queue'])

        fmt = '\n'.join(f'**`{str(song)}`**' for song in upcoming)
        embed = discord.Embed(title=f'Upcoming - Next {len(upcoming)}', description=fmt)

        await ctx.send(embed=embed)

        # num = 10
        #
        # fmt = '\n'.join(f'**`{str(song)}`**' for song in player.entries)
        # p = paginator.Pages(ctx, entries=tuple(track for track in player.entries), per_page=num)
        # p.embed.description = fmt
        # p.embed.set_author(name=_(ctx.lang, "Następne {} utworów").format(num),
        #              icon_url=self.bot.user.avatar_url)
        # await p.paginate(index_allowed=True)

        # await ctx.send(embed=e)

    @commands.command(name='shuffle', aliases=['mix'])
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def shuffle_(self, ctx):
        """Miesza piosenki w kolejce."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

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

        if await self.has_perms(ctx, manage_guild=True):
            if player.repeat:
                text = ctx.lang['off_vc_son']

            else:
                text = ctx.lang['on_vc_son']

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

    # @commands.command()
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

    @commands.command(aliases=['loop_queue'])
    @commands.cooldown(1, 10, commands.BucketType.guild)
    async def queue_loop(self, ctx):
        """Włącza powtarzanie kolejki."""
        player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

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

    @play.before_invoke
    @queue_loop.before_invoke
    @repeat_.before_invoke
    @shuffle_.before_invoke
    @queue_.before_invoke
    @volume.before_invoke
    @set_eq.before_invoke
    @skip_.before_invoke
    @resume_.before_invoke
    @disconnect.before_invoke
    @now_playing.before_invoke
    @pause_.before_invoke
    async def connect_handler(self, ctx):
        # player and member instances check
        if not ctx.author.voice:
            return await ctx.send(ctx.lang['arent_with_me_on_vc'])

        elif not ctx.guild.me.voice:
            return await ctx.send(ctx.lang['am_not_on_any_vc'])

        elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
            return await ctx.send(ctx.lang['arent_with_me_on_vc'])


def setup(bot):
    bot.add_cog(Music(bot))
