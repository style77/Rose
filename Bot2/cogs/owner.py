import collections
from psutil import Process
from os import getpid
from datetime import datetime

import discord
from discord.ext import commands

from jishaku.codeblocks import codeblock_converter
from jishaku.modules import ExtensionConverter

from .classes.other import Plugin

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

        return await ctx.send(file=discord.File("usage.png"))


def setup(bot):
    bot.add_cog(Owner(bot))
