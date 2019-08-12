import asyncio
import random
import traceback

import asyncpg
import dbl
import discord
import wavelink
import wrapper
from discord.ext import commands

from cogs.utils import utils

from cogs.classes import cache

OPTS = {'command_prefix': utils.get_pre,
        'description': 'Bot stworzony przez Style.\nv 1.0.1',
        'pm_help': False,
        'command_not_found': '',
        'case_insensitive': True}


class Bot(commands.AutoShardedBot):
    def __init__(self):
        super(Bot, self).__init__(**OPTS)

        self.development = utils.get_from_config('development')
        self.color = 0x8f0fba

        self.EXT = [
            'cogs.stars',
            'cogs.fun',
            'cogs.tags',
            'cogs.mod',
            'cogs.cat',
            'cogs.afk',
            'cogs.rr',
            'cogs.images',
            'cogs.help',
            'cogs.eh',
            'cogs.additional',
            'cogs.jishaku',
            'cogs.todo',
            'cogs.reminder',
            'cogs.nsfw',
            'cogs.music',
            'cogs.logs',
            'cogs.streams'
        ]
        self.loop.run_until_complete(self.create_db_pool())

        self.loop.create_task(self.changing())
        self.loop.create_task(self.caching_settings())

        self.token = utils.get_from_config("dbl")
        self.dblpy = dbl.Client(self, self.token)
        self.app = wrapper.Wrapper(token=utils.get_from_config("badoszapi"))

        self.wavelink = wavelink.Client(self)

        for extension in self.EXT:
            try:
                self.load_extension(extension)
            except Exception as cc_error:
                exc = '{}: {}'.format(type(cc_error).__name__, cc_error)
                print('Nie udało sie załadować {}\n{}.'.format(extension, exc))
                traceback.print_exc()

    async def caching_settings(self):
        await self.wait_until_ready()
        guilds = await self.pg_con.fetch("SELECT * FROM guild_settings")
        for guild in guilds:
            discord_guild = self.get_guild(guild['guild_id'])
            if discord_guild:
                cache.GuildSettingsCache().set(discord_guild, guild)

    # async def get_context(self, message, *, cls=None):
    # return await super().get_context(message, cls=Context)

    async def create_db_pool(self):
        self.pg_con = await asyncpg.create_pool(
            dsn=f"postgresql://{utils.get_from_config('dbip')}/{utils.get_from_config('dbname')}", user="style",
            password=utils.get_from_config("password"))

    async def get_blocked_commands(self, guild_id):
        blocked_commands = await self.pg_con.fetchval("SELECT blocked_commands FROM guild_settings WHERE guild_id = $1",
                                                      guild_id)
        return blocked_commands

    async def on_guild_join(self, guild):
        await self.pg_con.execute("UPDATE bot_count SET newest_guild = $1", guild.name)

    async def changing(self):
        await self.wait_until_ready()
        while not self.is_closed():
            if self.development:
                hearts = ['❤', '💛', '💚', '💜', '💖', '💙', '💞']
                await self.change_presence(status=discord.Status.dnd,
                                           activity=discord.Activity(type=discord.ActivityType.listening,
                                                                     name=f"Style {random.choice(hearts)}"))
                await asyncio.sleep(150)
            else:
                liczbaa = await self.pg_con.fetchrow("SELECT * FROM bot_count")
                newest_guild = liczbaa['newest_guild']
                newest_guild = f"{newest_guild} \U0001f440."
                liczba = liczbaa['messages']
                liczbac = liczbaa['commands']
                i = 0
                for _ in self.walk_commands():
                    i += 1
                v = await self.dblpy.get_bot_info()
                v = v['points']

                row = await self.pg_con.fetchrow("SELECT * FROM members WHERE id = $1", self.user.id)

                data = dict()
                data['online'] = row['online']
                data['offline'] = row['offline']
                data['idle'] = row['idle']
                data['dnd'] = row['dnd']

                total = sum(data.values())
                uptime = f"{(data['dnd'] / total) * 100:.2f}"
                # czas = timedelta(seconds=uptime())
                stats = [
                    "You.",
                    f"after {liczba} messages.",
                    f"{len(self.users)} members.",
                    f"{len(self.guilds)} guilds.",
                    f"after {liczbac} commands.",
                    "just read the docs.",
                    f"{i} commands!",
                    f"Style.",
                    f"{v} all votes.",
                    f"/invite",
                    f"/support",
                    "people usually forget about this bot in 5minutes.",
                    f"{uptime}% time online.",
                    "v1.3!",
                    newest_guild,
                ]

                status = random.choice(stats)
                listening_words = ['commands!', 'Style.', 'members', 'tags']
                if any(word in status for word in listening_words):
                    activity = discord.ActivityType.listening
                else:
                    activity = discord.ActivityType.watching
                await self.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=activity, name=status))
                await asyncio.sleep(250)

    async def on_ready(self):
        print(f'Logged in as {self.user.name} | {self.user.id}')