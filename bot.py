import discord
import asyncio
import asyncpg

import json
import os
import traceback
import random
import dbl
#import logging

import wrapper
import redis
import wavelink

from discord.ext import commands

from cogs.fun import uptime
from cogs.classes.context import Context
from cogs.utils import utils
from cogs.utils import dtab
from cogs.eh import MemberInBlacklist

from cogs.utils import translations

os.environ["JISHAKU_HIDE"] = "1"
os.environ["JISHAKU_NO_UNDERSCORE"] = "1"
os.environ["JISHAKU_RETAIN"] = "1"

#logger = logging.getLogger('discord')
#logger.setLevel(logging.DEBUG)
#handler = logging.FileHandler(
#    filename='discord.log', encoding='utf-8', mode='w')
#handler.setFormatter(logging.Formatter(
#    '%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
#logger.addHandler(handler)

OPTS = {'command_prefix': utils.get_pre,
        'description': 'Bot stworzony przez Style.\nv 1.0.1',
        'pm_help': False,
        'command_not_found': '',
        'case_insensitive': True}

class Blocked(commands.CommandError):
    pass

class Bot(commands.AutoShardedBot):
    def __init__(self):
        super(Bot, self).__init__(**OPTS)
        
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
            'cogs.music'
        ]
        self.loop.run_until_complete(self.create_db_pool())
        
        self.loop.create_task(self.changing())
        
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
                
    #async def get_context(self, message, *, cls=None):
        #return await super().get_context(message, cls=Context)

    async def create_db_pool(self):
        self.pg_con = await asyncpg.create_pool(dsn=f"postgresql://{utils.get_from_config('dbip')}/{utils.get_from_config('dbname')}", user="style", password=utils.get_from_config("password"))
        
    async def get_blocked_commands(self, guild_id):
        blocked_commands = await self.pg_con.fetchval("SELECT blocked_commands FROM guild_settings WHERE guild_id = $1", guild_id)
        return blocked_commands

    async def on_guild_join(self, guild):
        await self.pg_con.execute("UPDATE bot_count SET newest_guild = $1", guild.name)

    async def changing(self):
        await self.wait_until_ready()
        while not self.is_closed():
            liczbaa = await self.pg_con.fetchrow("SELECT * FROM bot_count")
            newest_guild = liczbaa['newest_guild']
            newest_guild = f"{newest_guild} thank you for inviting me!"
            liczba = liczbaa['messages']
            liczbac = liczbaa['commands']
            i = 0
            for _ in self.walk_commands():
                i += 1
            v = await self.dblpy.get_bot_info(self.user.id)
            v = v['points']
            row = await self.pg_con.fetchrow("SELECT * FROM members WHERE id = $1", self.user.id)
            data = dict()
            data['online'] = row['online']
            data['offline'] = row['offline']
            data['idle'] = row['idle']
            data['dnd'] = row['dnd']
            total = sum(data.values())
            uptime = f"{(data['dnd']/total)*100:.2f}"
            #czas = timedelta(seconds=uptime())
            stats = [
                "You.",
                f"after {liczba} messages.",
                f"{len(bot.users)} members.",
                f"{len(bot.guilds)} guilds.",
                f"after {liczbac} commands.",
                "just read the docs.",
                f"{i} commands!",
                f"Style.",
                f"{v} all votes.",
                f"vote on me please.",
                f"/invite",
                f"/support",
                f"/daily",
                f"/vote",
                "people usually forget about this bot in 5minutes.",
                "facts.",
                f"{uptime}% time online.",
                "v1.2!",
                newest_guild,
            ]

            status = random.choice(stats)
            listening_words = ['commands!', 'Style.', 'members', 'tags']
            #playing_words = ["for"]
            if any(word in status for word in listening_words):
                activity = discord.ActivityType.listening
            #elif any(word in status for word in playing_words):
                #activity = discord.ActivityType.playing
            else:
                activity = discord.ActivityType.watching
            await bot.change_presence(status=discord.Status.dnd, activity=discord.Activity(type=activity, name=status))
            await asyncio.sleep(250)

    async def on_ready(self):
        print(f'Logged in as {self.user.name} | {self.user.id}')

bot = Bot()

@bot.check
async def block_commands(ctx):
    if ctx.guild is None:
       return True
    blocked_commands_list = await ctx.bot.get_blocked_commands(ctx.guild.id)
    if not blocked_commands_list:
        return True
    if ctx.command.name.lower() not in blocked_commands_list:
        return True
    else:
        raise Blocked("{} is blocked.".format(ctx.command))

@bot.check
async def blacklist(ctx):
    blocked_members = await ctx.bot.pg_con.fetchrow("SELECT * FROM blacklist WHERE user_id = $1", ctx.author.id)
    if blocked_members:
        raise MemberInBlacklist()
    else:
        return True

@bot.before_invoke
async def get_lang(ctx):
    if not ctx.guild:
        ctx.lang = "ENG"
        return
    lang = await get_language(ctx.bot, ctx.guild.id)
    ctx.lang = lang

bot.run(utils.get_from_config("token"), reconnect=True)
