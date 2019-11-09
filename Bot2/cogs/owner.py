import collections
import textwrap

from psutil import Process
from os import getpid
from datetime import datetime

import discord
from discord.ext import commands

from jishaku.codeblocks import codeblock_converter
from jishaku.modules import ExtensionConverter

from .classes.other import Plugin

from tabulate import tabulate
import matplotlib.pyplot as plt


class Owner(Plugin, command_attrs=dict(hidden=True)):

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    @commands.command(name="eval")
    async def eval_(self, ctx, *, body: codeblock_converter):
        return await ctx.invoke(self.bot.get_command("jishaku python"), argument=body)

    @commands.command(aliases=["r"])
    async def reload(self, ctx, *extensions: ExtensionConverter):
        return await ctx.invoke(self.bot.get_command("jishaku reload"), *extensions)

    @commands.command()
    async def ping(self, ctx):
        await ctx.send(f"{ctx.lang['ping_message']}")

    @commands.command(aliases=['socket_stats'])
    async def socketstats(self, ctx):
        delta = datetime.utcnow() - self.bot.uptime
        minutes = delta.total_seconds() / 60
        total = sum(self.bot.socket_stats.values())
        cpm = total / minutes

        stats = [f"{event}: {x}" for event, x in self.bot.socket_stats.most_common()]
        z = '\n'.join(stats)

        await ctx.send(f"{total} {ctx.lang['sockets_observed']} ({cpm:.2f}/minute):\n```{z}```")

    @commands.command(aliases=['machine_stats', 'usage'])
    async def machinestats(self, ctx):
        text = f"Used RAM: {round(Process(getpid()).memory_info().rss/1024/1024, 2)} MB.\n" \
               f"Guilds: {len(self.bot.guilds)}.\n" \
               f"Users: {len(self.bot.users)}.\n"

        await ctx.send('```\n' + text + '```')

    @commands.command(aliases=['cmds_usage'])
    async def commands_usage(self, ctx):
        plt.clf()

        usage = collections.OrderedDict(sorted(self.bot.usage.items(), key=lambda kv: kv[1], reverse=True))

        plt.bar([k for k in usage.keys()], [v for v in usage.values()])

        plt.ylabel("Usage")
        plt.xlabel("Commands")

        plt.xticks(rotation=90)
        plt.savefig("usage.png")

        return await ctx.send(file=discord.File("assets/images/usage.png"))

    @commands.group(invoke_without_command=True)
    async def sql(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @sql.command(hidden=True)
    async def execute(self, ctx, *, query: codeblock_converter = None):
        query = query.content

        if "_author.id" in query:
            query = query.replace("_author.id", str(ctx.author.id))
        if "_guild.id" in query:
            query = query.replace("_guild.id", str(ctx.guild.id))
        try:
            e = await self.bot.db.execute(query)
        except Exception as er:
            e = f"{type(er)} - {er}"
        await ctx.send(e)

    @sql.command(hidden=True)
    async def fetch(self, ctx, *, query: codeblock_converter = None):
        query = query.content

        if "_author.id" in query:
            query = query.replace("_author.id", str(ctx.author.id))
        if "_guild.id" in query:
            query = query.replace("_guild.id", str(ctx.guild.id))
        try:
            e = await self.bot.db.fetch(query)
        except Exception as er:
            e = f"{type(er)} - {er}"
        await ctx.send(e)

    @commands.group(invoke_without_command=True)
    async def rose(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @rose.group(invoke_without_command=True)
    async def get(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @rose.group(invoke_without_command=True)
    async def update(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @get.command()
    async def guild(self, ctx, guild):
        if guild in ["this", "self"]:
            guild = ctx.guild
        else:
            guild = discord.utils.get(self.bot.guilds, id=guild)

        g = await self.bot.get_guild_settings(guild.id)

        table = []
        keys = ["guild", "data"]

        for key, value in g.data.items():
            table.append([key, value])

        p = commands.Paginator()

        z = f"{tabulate(table, keys, tablefmt='github')}"

        for line in z.splitlines():
            p.add_line(line)

        for page in p.pages:
            await ctx.send(page)

    @update.command(name="guild")
    async def guild_(self, ctx, guild, key, *, value):
        if guild in ["this", "self"]:
            guild = ctx.guild
        else:
            guild = discord.utils.get(self.bot.guilds, id=guild)

        if value.isdigit():
            value = int(value)
        else:
            value = value

        g = await self.bot.get_guild_settings(guild.id)
        z = await g.set(key, value)

        await ctx.send(z)


def setup(bot):
    bot.add_cog(Owner(bot))
