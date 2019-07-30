import asyncio
import datetime
import discord
import humanize
import itertools
import re
import sys
import traceback
import wavelink
import random
from discord.ext import commands
from typing import Union

RURL = re.compile(r"https?:\/\/(?:www\.)?.+")

class MusicController:
    def __init__(self, bot, guild_id):
        self.bot = bot
        self.guild_id = guild_id
        self.channel = None

        self.next = asyncio.Event()
        self.queue = asyncio.Queue()

        self.volume = 40
        self.now_playing = None
        self.repeating = False

        self.bot.loop.create_task(self.controller_loop())

    @property
    def entries(self):
        return list(self.queue._queue)

    async def controller_loop(self):
        await self.bot.wait_until_ready()

        player = self.bot.wavelink.get_player(self.guild_id)
        await player.set_volume(self.volume)

        while True:
            if self.now_playing:
                await self.now_playing.delete()

            self.next.clear()

            song = await self.queue.get()
            await player.play(song)
            self.now_playing = await self.channel.send(_(await get_lang(self.bot, self.guild_id), "Teraz gra: {}.").format(song))

            await self.next.wait()


class Music(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.controllers = {}

        if not hasattr(bot, 'wavelink'):
            self.bot.wavelink = wavelink.Client(self.bot)

        self.bot.loop.create_task(self.start_nodes())

    async def start_nodes(self):
        await self.bot.wait_until_ready()

        # Initiate our nodes. For this example we will use one server.
        # Region should be a discord.py guild.region e.g sydney or us_central (Though this is not technically required)
        node = await self.bot.wavelink.initiate_node(host='0.0.0.0',
                                                     port=1334,
                                                     rest_uri='http://0.0.0.0:1334',
                                                     password='youshallnotpass',
                                                     region='us_central',
                                                     identifier='style')

        # Set our node hook callback
        node.set_hook(self.on_event_hook)

    async def on_event_hook(self, event):
        if isinstance(event, (wavelink.TrackEnd, wavelink.TrackException)):
            controller = self.get_controller(event.player)
            controller.next.set()

    def get_controller(self, value: Union[commands.Context, wavelink.Player]):
        if isinstance(value, commands.Context):
            gid = value.guild.id
        else:
            gid = value.guild_id

        try:
            controller = self.controllers[gid]
        except KeyError:
            controller = MusicController(self.bot, gid)
            self.controllers[gid] = controller

        return controller

    async def __local_check(self, ctx):
        if not ctx.guild:
            raise commands.NoPrivateMessage
        return True

    @commands.command(name='connect', aliases=['join'])
    async def connect_(self, ctx, *, channel: discord.VoiceChannel=None):
        if not channel:
            try:
                channel = ctx.author.voice.channel
            except AttributeError:
                return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Nie jesteś na kanale."))

        player = self.bot.wavelink.get_player(ctx.guild.id)
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Łączenie z {}.").format(channel.name))
        await player.connect(channel.id)
        await ctx.guild.me.edit(deafen=True)

        controller = self.get_controller(ctx)
        controller.channel = ctx.channel

    @commands.command(aliases=['p'])
    async def play(self, ctx, *, query: str):
        if not RURL.match(query):
            query = f'ytsearch:{query}'

        tracks = await self.bot.wavelink.get_tracks(f'{query}')

        if not tracks:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Nie znaleziono takiej piosenki."))

        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_connected:
            await ctx.invoke(self.connect_)

        track = tracks[0]

        controller = self.get_controller(ctx)
        await controller.queue.put(track)
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Dodano {} do kolejki.").format(str(track)))

    @commands.command()
    async def pause(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.is_playing:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Aktualnie nic nie gra."))

        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Zatrzymuje piosenkę."))
        await player.set_pause(True)

    @commands.command(aliases=['r'])
    async def resume(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        if not player.paused:
            return await ctx.send("Odtwarzacz nie jest obecnie wstrzymany.")

        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Wznawianie odtwarzacza."))
        await player.set_pause(False)

    @commands.command()
    async def skip(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if not player.is_playing:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Aktualnie nic nie gra."))

        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Pomijanie piosenki."))
        await player.stop()

    @commands.command(aliases=['vol'])
    async def volume(self, ctx, *, vol: int):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        vol = max(min(vol, 500), 0)
        controller.volume = vol

        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Ustawianie głośności odtwarzacza na {}.").format(vol))
        await player.set_volume(vol)

    @commands.command(aliases=['np', 'current', 'nowplaying'])
    async def now_playing(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if not player.current:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Aktualnie nic nie gra."))

        controller = self.get_controller(ctx)

        controller.now_playing = await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Teraz gra: {}." + f" {'🔂' if controller.repeating else ''}").format(player.current))

    @commands.command(aliases=['q'])
    async def queue(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        if not player.current or not controller.queue._queue:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "W kolejce nie ma obecnie żadnych utworów."))

        upcoming = list(itertools.islice(controller.queue._queue, 0, 5))

        fmt = '\n'.join(f'**`{str(song)}`**' for song in upcoming)
        embed = discord.Embed(title=_(await get_lang(self.bot, ctx.guild.id), "Następne {}").format(len(upcoming)), description=fmt)

        await ctx.send(embed=embed)

    @commands.command(aliases=['disconnect', 'dc'])
    async def stop(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        try:
            del self.controllers[ctx.guild.id]
        except KeyError:
            await player.disconnect()

        await player.disconnect()
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Rozłączono."))

    @commands.command()
    @commands.is_owner()
    async def info(self, ctx):
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
              f'Server Uptime: `{datetime.timedelta(milliseconds=node.stats.uptime)}`'
        await ctx.send(fmt)

    @commands.command(name='repeat', aliases=['l', 'loop'], enabled=False)
    async def repeat_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if not player.is_connected:
            return

        #if await self.has_perms(ctx, manage_guild=True):
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "{} włączył powtarzanie utworu jako administrator lub DJ.").format(ctx.author.mention))
        return await self.do_repeat(ctx)

        #await self.do_vote(ctx, player, 'repeat')

    async def do_repeat(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        if not controller.entries:
            await controller.queue.put(player.current)
        else:
            controller.queue._queue.appendleft(player.current)

        player.update = True
        controller.repeating = True

    @commands.command(name='shuffle', aliases=['mix'], enabled=False)
    @commands.cooldown(2, 10, commands.BucketType.user)
    async def shuffle_(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)

        if not player.is_connected:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Nie jestem połączony z kanałem."))

        if len(controller.entries) < 3:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Dodaj więcej utworów do kolejki, zanim spróbujesz przetasować playliste."))

        #if await self.has_perms(ctx, manage_guild=True):
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "{} przetasował kolejkę odtwarzania jako administrator lub DJ.").format(ctx.author.mention))
        return await self.do_shuffle(ctx)

        #await self.do_vote(ctx, player, 'shuffle')

    async def do_shuffle(self, ctx):
        player = self.bot.wavelink.get_player(ctx.guild.id)
        controller = self.get_controller(ctx)
        random.shuffle(controller.queue._queue)

        player.update = True

    @commands.command(name='seteq', aliases=['eq'])
    async def set_eq(self, ctx, *, eq: str):
        player = self.bot.wavelink.get_player(ctx.guild.id)

        if eq.upper() not in player.equalizers:
            return await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "{} - Nie jest prawidłowym equalizerem!\nSpróbuj Flat, Boost, Metal, Piano.").format(eq))

        await player.set_preq(eq)
        player.eq = eq.capitalize()
        await ctx.send(_(await get_lang(self.bot, ctx.guild.id), "Equalizer został ustawiony na - {}.").format(eq.capitalize()))

def setup(bot):
    bot.add_cog(Music(bot))
