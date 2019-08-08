import json

import math
import operator
import builtins
import inspect
import ast

from yaml import load, Loader
from discord.ext import commands

from functools import lru_cache


def get_from_config(thing):
    with open(r"config.yml", 'r') as f:
        cfg = load(f, Loader=Loader)
    return cfg[thing]


async def get_pre(bot, message):
    if bot.development and message.author.id == bot.owner_id:
        return "!"

    if not message.guild:
        return ""

    get_prefix = await bot.pg_con.fetchrow(
        "SELECT * FROM prefixes WHERE guild_id = $1", message.guild.id)
    if not get_prefix:
        return "/"

    return [f"{get_prefix['prefix']} ", get_prefix['prefix']]


def check_permissions(*, allow_owner=True, **permissions):
    def inner(func):
        async def predicate(ctx):
            if allow_owner and await ctx.bot.is_owner(ctx.author):
                return True
            perms = ctx.channel.permissions_for(ctx.author)
            missing = [perm for perm, value in permissions.items(
            ) if getattr(perms, perm, None) != value]
            if not missing:
                return True
            raise commands.MissingPermissions(missing)
        func.required_permissions = list(permissions)
        return commands.check(predicate)(func)
    return inner


builtins.check_permissions = check_permissions
