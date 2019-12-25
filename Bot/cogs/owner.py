import collections
import textwrap
import importlib
import sys
import time
from io import BytesIO

import json

from psutil import Process
from os import getpid
from datetime import datetime

import discord
from discord.ext import commands

from jishaku.codeblocks import codeblock_converter
from jishaku.modules import ExtensionConverter

from .custom_jishaku import Jishaku

from .classes.other import Plugin

from tabulate import tabulate
# import matplotlib.pyplot as plt


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

        # stats = [f"{event}: {x}" for event, x in self.bot.socket_stats.most_common()]
        # z = '\n'.join(stats)

        z = ""
        for event, x in self.bot.socket_stats.most_common():
            z += f"{event}:{' ' * int(21 - len(str(event)))}{x}\n"

        await ctx.send(f"{total} {ctx.lang['sockets_observed']} ({cpm:.2f}/minute):\n```{z}```")

    @commands.command(aliases=['machine_stats', 'usage'])
    async def machinestats(self, ctx):
        text = f"Used RAM: {round(Process(getpid()).memory_info().rss/1024/1024, 2)} MB.\n" \
               f"Guilds: {len(self.bot.guilds)}.\n" \
               f"Users: {len(self.bot.users)}.\n"

        await ctx.send('```\n' + text + '```')

    # @staticmethod
    # def do_bar_chart(title, x_label, y_label, values, names):

    #     # Clear the plot.
    #     plt.clf()

    #     # Create a bar graph with grid lines
    #     plt.bar(names, values, width=0.5, zorder=3)
    #     plt.grid(zorder=0)

    #     # Add labels
    #     plt.ylabel(y_label)
    #     plt.xlabel(x_label)
    #     plt.title(title)

    #     # Rotate x-labels by 90 degrees
    #     plt.xticks(rotation=-90)

    #     # Make the layout of plot conform to the text
    #     plt.tight_layout()

    #     # Save the image to a buffer.
    #     bar_chart = BytesIO()
    #     plt.savefig(bar_chart)

    #     # Close the image.
    #     plt.close()

    #     # Return image
    #     bar_chart.seek(0)
    #     return bar_chart

    # @commands.command(aliases=['cmds_usage'])
    # async def commands_usage(self, ctx):
    #     usage = collections.OrderedDict(sorted(self.bot.usage.items(), key=lambda kv: kv[1], reverse=True))

    #     start = time.perf_counter()

    #     bar_chart = self.do_bar_chart("Command usage", "Command", "Usage", [v for v in usage.values()],
    #                                   [k for k in usage.keys()])
    #     end = time.perf_counter()
    #     await ctx.send(f"Done in {end - start:.3f}s", file=discord.File(filename=f"StatsBar.png", fp=bar_chart))

    @commands.command()
    async def reload_languages(self, ctx):
        with open(r"assets/languages/eng.json") as f:
            self.bot.english = json.load(f)

        with open(r"assets/languages/pl.json") as f:
            self.bot.polish = json.load(f)
        await ctx.send(':ok_hand:')

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
            guild = self.bot.get_guild(int(guild))

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

    @get.command()
    async def cat(self, ctx, cat):
        if cat in ["this", "self"]:
            cat = ctx.author.id

        table = []
        keys = ["cat_owner", "data"]

        cat_ = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", cat)

        for key, value in cat_.items():
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
            guild = self.bot.get_guild(int(guild))

        if value.isdigit():
            value = int(value)
        else:
            value = value

        g = await self.bot.get_guild_settings(guild.id)
        z = await g.set(key, value)

        await ctx.send(z)

    @update.command(name="cat")
    async def cat_(self, ctx, cat_owner, key, *, value):
        if cat_owner in ["me", "self"]:
            cat_owner = ctx.author
        else:
            cat_owner = await commands.MemberConverter().convert(ctx, cat_owner)
            if not cat_owner:
                return await ctx.send("No person like that.")

        cat = await self.bot.get_cog('Cat').get_cat(cat_owner)

        if value.isdigit:
            value = int(value)

        z = await self.bot.db.execute(f"UPDATE cats SET {key} = $1 WHERE owner_id = $2", value, cat_owner.id)
        await ctx.send(z)

    @commands.command()
    async def disable(self, ctx, command):
        cmd = self.bot.get_command(command)
        if not cmd:
            return await ctx.send(f"Command `{command}` not found")

        cmd.enabled = False
        await ctx.send(":ok_hand:")

    @commands.command()
    async def enable(self, ctx, command):
        cmd = self.bot.get_command(command)
        if not cmd:
            return await ctx.send(f"Command `{command}` not found")

        cmd.enabled = True
        await ctx.send(":ok_hand:")


def setup(bot):
    bot.add_cog(Jishaku(bot))
    bot.add_cog(Owner(bot))
