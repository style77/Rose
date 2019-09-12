import asyncio
import os
import random
import traceback

import asyncpg
import dbl
import discord
import wavelink
import wrapper
from discord.ext import commands

from cogs.eh import MemberInBlacklist
from cogs.utils import utils
from cogs.classes import cache
from cogs.classes.bot import Bot

from cogs.utils import translations

os.environ["JISHAKU_HIDE"] = "1"
os.environ["JISHAKU_NO_UNDERSCORE"] = "1"
os.environ["JISHAKU_RETAIN"] = "1"


class Blocked(commands.CommandError):
    pass


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
    if not blocked_members:
        return True
    if blocked_members:
        raise MemberInBlacklist()
    else:
        return True


@bot.check
async def plugins(ctx):
    if not ctx.guild:
        return True

    plugins_off = await ctx.bot.pg_con.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
    if not plugins_off:
        return True

    if not ctx.cog:
        return True
    if ctx.cog.qualified_name in plugins_off[0]:
        return False
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
