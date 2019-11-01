import asyncio
import json
import random
import traceback
from datetime import datetime
from collections import Counter

import asyncpg
import discord

from discord.ext import commands, tasks

from ..utils.misc import get_prefix, get
from .guild import Guild
from .context import RoseContext

OPTS = {'command_prefix': get_prefix,
        'description': 'Bot stworzony przez Style#0011.\nv2.0',
        'pm_help': False,
        'command_not_found': '',
        'case_insensitive': True}


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super(Bot, self).__init__(**OPTS)

        # tasks
        self._connect_database.start()
        self._load_extensions.start()
        self.changing.start()

        with open(r"assets/languages/eng.json") as f:
            self.english = json.load(f)

        with open(r"assets/languages/pl.json") as f:
            self.polish = json.load(f)

        self._config = {'token': get('token'),
                        'support': get('support_server')}

        self.development = get('development')
        self.color = get('color')

        self.context = None  # this *could* be very functional
        self.socket_stats = Counter()
        self.uptime = datetime.utcnow()

        self.exts = list()

        self.usage = Counter()

        self._settings_cache = dict()

    async def on_message(self, message):
        ctx = await self.get_context(message, cls=RoseContext)
        await self.invoke(ctx)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=cls or RoseContext)

    # noinspection PyCallingNonCallable
    @tasks.loop(count=1)
    async def _connect_database(self):
        self.db = await asyncpg.create_pool(
            dsn=f"postgresql://{get('dbip')}/{get('dbname')}", user="style",
            password=get("password"))

    # noinspection PyCallingNonCallable
    @tasks.loop(count=1)
    async def _load_extensions(self):
        for module in self.exts:
            try:
                self.load_extension(f"cogs.{module}")
            except Exception as e:
                traceback.print_exc()

    async def get_guild_settings(self, guild_id):
        raw_guild_settings = await self.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
        if raw_guild_settings is None:
            raw_guild_settings = await self.add_guild_to_database(guild_id)

        return Guild(self, raw_guild_settings)

    async def add_guild_to_database(self, guild_id):
        new_guild = await self.db.execute("INSERT INTO guild_settings (guild_id) VALUES ($1) RETURNING *", guild_id)
        return new_guild

    async def clear_settings(self, guild_id):
        await self.db.execute("DELETE FROM guild_settings WHERE guild_id = $1", guild_id)
        await self.db.execute("DELETE FROM streams WHERE guild_id = $1", guild_id)

    @tasks.loop(count=1)
    async def changing(self):
        if self.development:
            hearts = ['❤', '💛', '💚', '💜', '💖', '💙', '💞']
            await self.change_presence(status=discord.Status.dnd,
                                       activity=discord.Activity(type=discord.ActivityType.listening,
                                                                 name=f"Style {random.choice(hearts)}"))
            await asyncio.sleep(150)
        else:
            count = await self.db.fetchrow("SELECT * FROM bot_count")

            all_messages = count['messages']
            all_commands = count['commands']

            total_commands = [i for i in self.walk_commands()]

            all_tags = await self.db.fetch("SELECT * FROM tags")

            stats = [
                "You.",
                f"after {all_messages} messages.",
                f"{len(self.users)} members.",
                f"{len(self.guilds)} guilds.",
                f"after {all_commands} commands.",
                f"{len(total_commands)} total commands!",
                f"Add me! /invite",
                f"Join! /support",
                "people usually forget about this bot in 5minutes.",
                f"{len(all_tags)} tags."
            ]

            status = random.choice(stats)
            listening_words = ['commands!', 'Style.', 'members', 'tags']
            if any(word in status for word in listening_words):
                activity = discord.ActivityType.listening
            else:
                activity = discord.ActivityType.watching
            await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=activity,
                                                                                            name=status))
            await asyncio.sleep(250)

    @changing.before_loop
    async def changing_before(self):
        await self.wait_until_ready()

    async def on_ready(self):
        print(f'Logged in as {self.user.name} | {self.user.id}')