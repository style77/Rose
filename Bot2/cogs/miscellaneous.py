import os
import re

import aiohttp
import discord
from discord.ext import commands
from io import BytesIO

from .classes.converters import SafeConverter
from .utils import SphinxObjectFileReader
from .classes.other import Plugin


class Useful(Plugin):
    """Make your life easier."""
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @commands.command(aliases=['yn'])
    async def yesno(self, ctx, *, option: SafeConverter):
        """Yes or No"""
        reactions = ['✅', '❌']

        e = discord.Embed(description=option, color=0x36393E)
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")

        msg = await ctx.send(embed=e)

        for r in reactions:
            await msg.add_reaction(r)

    @commands.command()
    async def poll(self, ctx, *options: SafeConverter):
        """Tworzy głosowanie z max 10 opcjami."""
        if len(options) == 0:
            return commands.UserInputError()
        if len(options) == 1:
            return await ctx.invoke(self.bot.get_command("yn"), option=''.join(options))
        elif len(options) <= 10:
            i = len(options)
            c = 0
            reactions = []
            numbers = [
                '1\N{combining enclosing keycap}',
                '2\N{combining enclosing keycap}',
                '3\N{combining enclosing keycap}',
                '4\N{combining enclosing keycap}',
                '5\N{combining enclosing keycap}',
                '6\N{combining enclosing keycap}',
                '7\N{combining enclosing keycap}',
                '8\N{combining enclosing keycap}',
                '9\N{combining enclosing keycap}',
                '\N{keycap ten}'
                    ]
            while c < i:
                reactions.append(numbers[c])
                c += 1
            index = 0
            msg = []
            for _ in options:
                msg.append(f"{index+1}. {options[index]}")
                index += 1
            msg = '\n'.join(msg)
        else:
            return await ctx.send(ctx.lang['max_options_10'])

        e = discord.Embed(description=msg, color=0x36393E)
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")

        msg = await ctx.send(embed=e)

        for r in reactions:
            await msg.add_reaction(r)

    @commands.command()
    async def tree(self, ctx):
        """Zwraca drzewko z kanałami."""
        a = commands.Paginator()
        for b in ctx.guild.categories:
            a.add_line("📘 {0}".format(b))
            for e in b.channels:
                a.add_line(
                    f"-   {'📝' if isinstance(e, discord.TextChannel) else '🔈'} #{e}")
        for p in a.pages:
            await ctx.send(p)

    @staticmethod
    def parse_object_inv(stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError(
                'Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(
            r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.',
                                  '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        'Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    @staticmethod
    def finder(text, collection, *, key=None, lazy=True):
        suggestions = []
        text = str(text)
        pat = '.*?'.join(map(re.escape, text))
        regex = re.compile(pat, flags=re.IGNORECASE)
        for item in collection:
            to_search = key(item) if key else item
            r = regex.search(to_search)
            if r:
                suggestions.append((len(r.group()), r.start(), item))

        def sort_key(tup):
            if key:
                return tup[0], tup[1], key(tup[2])
            return tup

        if lazy:
            return (z for _, _, z in sorted(suggestions, key=sort_key))
        else:
            return [z for _, _, z in sorted(suggestions, key=sort_key)]

    async def do_rtfm(self, ctx, key, obj):
        page_types = {
            'latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
        }

        if obj is None:
            return await ctx.send(page_types[key])

        if not hasattr(self, '_rtfm_cache'):
            await ctx.trigger_typing()
            await self.build_rtfm_lookup_table(page_types)

        obj = re.sub(
            r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

        if key.startswith('latest'):
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = f'abc.Messageable.{name}'
                    break

        cache = list(self._rtfm_cache[key].items())

        matches = self.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

        e = discord.Embed()
        if len(matches) == 0:
            return await ctx.send(ctx.lang['nothing_found'])

        e.description = '\n'.join(f'[{key}]({url})' for key, url in matches)
        await ctx.send(embed=e)

    @commands.group(aliases=['rtfd'], invoke_without_command=True)
    async def rtfm(self, ctx, *, obj: str = None):
        await self.do_rtfm(ctx, 'latest', obj)

    @rtfm.command(name='python', aliases=['py'])
    async def rtfm_python(self, ctx, *, obj: str = None):
        await self.do_rtfm(ctx, 'python', obj)


def setup(bot):
    bot.add_cog(Useful(bot))
