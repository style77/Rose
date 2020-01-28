import asyncio
import json
import os
import random
import traceback
from datetime import datetime
from collections import Counter

import aiohttp
import aioredis
import asyncpg
import discord
import wavelink

from discord.ext import commands, tasks

from .user import User
from ..utils.misc import get_prefix, get, get_language
from .guild import Guild
from .context import RoseContext
from .database import Database

OPTS = {'command_prefix': get_prefix,
        'description': 'Bot stworzony przez Style#0011.\nv2.0',
        'pm_help': False,
        'command_not_found': '',
        'case_insensitive': True}


class LanguageObject:
    def __init__(self, raw_object):
        self.raw_object = raw_object
        
    def __getitem__(self, item):
        try:
            return self.raw_object[item]
        except KeyError:
            return item


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super(Bot, self).__init__(**OPTS)

        # tasks
        self._connect_databases.start()
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

        self.wavelink = wavelink.Client(self)

        self.exts = list()

        self.usage = Counter()

        self._settings_cache = dict()
        self._users_cache = dict()  # todo

        self.session = aiohttp.ClientSession(loop=self.loop)

    async def on_message(self, message):
        ctx = await self.get_context(message, cls=RoseContext)
        if not message.guild:
            language = "ENG"
        else:
            guild = await self.get_guild_settings(message.guild.id)
            language = guild.language
        
        raw_lang = self.get_language_object(language)
        ctx.lang = LanguageObject(raw_lang)
        await self.invoke(ctx)

    def get_language_object(self, lang):
        raw_lang = self.polish if lang == "PL" else self.english
        return raw_lang

    def __validate_languages(self):
        z = list()
        i = 1

        for key in self.polish.keys():
            i += 1
            if key not in self.english.keys():
                z.append(f"LINE {i} | {key} not found in _eng.json")
            elif self.polish[key] == self.english[key]:
                z.append(f"LINE {i} | {key} not translated.")

        return z

    # noinspection PyCallingNonCallable
    @tasks.loop(count=1)
    async def _connect_databases(self):
        self.db = await asyncpg.create_pool(
            dsn=f"postgresql://{get('dbip')}/{get('dbname')}", user="style",
            password=get("password"))

        self.redis = await aioredis.create_redis_pool('redis://localhost:6379')

        # self.db = Database(self, poll)

    # noinspection PyCallingNonCallable
    @tasks.loop(count=1)
    async def _load_extensions(self):
        for module in self.exts:
            try:
                path = os.path.abspath(f"cogs/{module}.py").replace("/", ".")
                path = path.replace(".py", "")

                path = list(path)
                path[0] = ""
                path = ''.join(path)

                self.load_extension(f"cogs.{module}")
            except Exception as e:
                traceback.print_exc()

    async def get_guild_settings(self, guild_id):
        if not guild_id:
            return

        if guild_id not in self._settings_cache:
            raw_guild_settings = await self.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
            if raw_guild_settings is None:
                raw_guild_settings = await self.add_guild_to_database(guild_id)
            g = Guild(self, raw_guild_settings)
            self._settings_cache[guild_id] = g
        else:
            g = self._settings_cache.get(guild_id)
        return g

    async def fetch_user_from_database(self, user_id):
        user = await self.db.fetchrow("SELECT * FROM users WHERE id = $1;", user_id)
        if user:
            return User(self, user)
        else:
            return User(self, await self.add_user(user_id))

    async def add_user(self, user_id):
        query = "INSERT INTO users (id) VALUES ($1) RETURNING *;"
        return await self.db.fetchrow(query, user_id)

    async def add_guild_to_database(self, guild_id):
        if not guild_id:
            return

        new_guild = await self.db.fetchrow("INSERT INTO guild_settings (guild_id) VALUES ($1) RETURNING *;", guild_id)
        return new_guild

    async def clear_settings(self, guild_id):
        await self.db.execute("DELETE FROM guild_settings WHERE guild_id = $1;", guild_id)
        await self.db.execute("DELETE FROM streams WHERE guild_id = $1;", guild_id)

    @tasks.loop(seconds=150)
    async def changing(self):
        if self.development:
            hearts = ['❤', '💛', '💚', '💜', '💖', '💙', '💞']
            await self.change_presence(status=discord.Status.dnd,
                                       activity=discord.Activity(type=discord.ActivityType.listening,
                                                                 name=f"Style {random.choice(hearts)}"))
            await asyncio.sleep(150)
        else:
            count = await self.db.fetchrow("SELECT * FROM count")

            all_messages = 0
            all_commands = 0

            for g in count:
                all_messages += g['messages']
                all_commands += g['commands']

            total_commands = [i for i in self.walk_commands()]

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
                f"V2."
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
        print('\n'.join(self.__validate_languages()))
