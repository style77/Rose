import os
import re
from datetime import datetime

import aiohttp
import discord
import typing
import functools

import humanize
from bs4 import BeautifulSoup
from discord.ext import commands
from io import StringIO

from .classes.converters import SafeConverter
from .utils import SphinxObjectFileReader
from .classes.other import Plugin
from .utils import get_language


class Useful(Plugin):
    """Make your life easier."""
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    def processing(self, history):
        buf = StringIO()
            
        for i, message in enumerate(history):
            content = message.content
            
            if message.attachments:
                content = message.attachments[0].url
            if message.embeds:
                e = message.embeds[0]
                content = "embed"
                
            if not content:
                continue
                
            buf.write(
                f"#{i+1} {message.channel.name}  -  {message.author}: {content}  / {str(message.created_at)}\n")

        buf.seek(0)
        return buf

    @commands.command()
    async def history(self, ctx, limit=50):
        """Zwraca plik z historią wiadomości."""
        
        history = []
        
        async with ctx.channel.typing():
            async for message in ctx.channel.history(limit=limit):
                history.append(message)
        
        func = functools.partial(self.processing, history)
        
        buf = await self.bot.loop.run_in_executor(None, func)
        
        file = discord.File(filename=f"{ctx.channel.name}.txt", fp=buf)
        await ctx.send(file=file)

    @commands.command(aliases=["avy", "awatar"])
    async def avatar(self, ctx, member: discord.Member = None):
        member = member or ctx.author

        e = discord.Embed(color=member.color)
        e.set_image(url=member.avatar_url)
        e.set_author(name=member)
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
        await ctx.send(embed=e)

    @commands.command(name="user", aliases=["member", "userinfo"])
    async def user_info(self, ctx, user: discord.Member = None):
        """Zwraca informacje o koncie Discord, twoim bądź osoby oznaczonej."""
        if ctx.message.author.bot:
            return

        user = user or ctx.author
        userjoinedat = str(user.joined_at).split('.', 1)[0]
        usercreatedat = str(user.created_at).split('.', 1)[0]
        shared = sum(g.get_member(user.id) is not None for g in self.bot.guilds)

        userembed = discord.Embed(
            description=user.display_name + ("<:bottag:597838054237011968>" if user.bot else ''),
            color=user.color,
            timestamp=ctx.message.created_at)
        userembed.set_author(
            name=user.name, icon_url=user.avatar_url)
        userembed.set_thumbnail(url=user.avatar_url)
        userembed.add_field(name=ctx.lang['joined_server'], value=userjoinedat)
        userembed.add_field(name=ctx.lang['created_account'], value=usercreatedat)
        if user.activity:
            userembed.add_field(name=ctx.lang['playing'], value=user.activity.name)
        userembed.add_field(name=ctx.lang['shared_servers'], value=shared)
        if user.status is not None:
            userembed.add_field(name="Status", value=f'{user.status}')
        userembed.add_field(name=ctx.lang['rank_color'], value=f'`{user.color}`')
        userembed.add_field(name="Tag", value=f'`{user.discriminator}`')
        userembed.add_field(name=ctx.lang['highest_rank'], value=user.top_role.mention)
        userembed.add_field(name=ctx.lang['ranks'], value=', '.join([r.mention for r in user.roles]))

        user_ = await self.bot.fetch_user_from_database(user.id)
        if user_:
            fmt = "{}    {}"
            z = []

            if user_.last_nicknames:
                if str(ctx.guild.id) in user_.last_nicknames:
                    nicks = user_.last_nicknames[str(ctx.guild.id)]
                    for nick, data in nicks.items():
                        if nick == "null":
                            nick = ctx.author.name
                        date = datetime.fromtimestamp(data['changed'])
                        t = date.strftime("%d %b %Y %H:%M")
                        z.append(fmt.format(f"{t} UTC", nick))

                    userembed.add_field(name=ctx.lang['nicks'], value="```" + '\n'.join(z) + "```", inline=False)

            if user_.last_usernames:
                nicks = user_.last_usernames
                for nick, data in nicks.items():
                    if nick == "null":
                        nick = ctx.author.name
                    date = datetime.fromtimestamp(data['changed'])
                    t = date.strftime("%d %b %Y %H:%M")
                    z.append(fmt.format(f"{t} UTC", nick))

                    userembed.add_field(name=ctx.lang['usernames'], value="```" + '\n'.join(z) + "```", inline=False)

        userembed.set_footer(text=f'ID: {user.id}')
        await ctx.send(embed=userembed)

    @commands.command(aliases=["amionmobile?"])
    async def amionmobile(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        if member.is_on_mobile():
            await ctx.send(ctx.lang['yes'])
        else:
            await ctx.send(ctx.lang['no'])

    @commands.command(name="firstmsg", aliases=["firstmessage", "first_message", "first_msg"])
    async def first_message(self, ctx, channel: discord.TextChannel = None):
        """Pierwsza wiadomość z danego kanału."""
        channel = channel or ctx.channel

        first_message = (await channel.history(limit=1, oldest_first=True).flatten())[0]

        embed = discord.Embed(title=f"#{channel}", description=first_message.content, timestamp=first_message.created_at)
        embed.set_author(name=str(first_message.author), icon_url=first_message.author.avatar_url)
        embed.add_field(name="\u200b", value=f"[Jump!]({first_message.jump_url})")

        await ctx.send(embed=embed)

    @commands.command(aliases=["hb", "note"])
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def hastebin(self, ctx, *, content):
        async with self.bot.session.post("https://hastebin.com/documents", data=content.encode('utf-8')) as post:
            post = await post.json()

        url = f"https://hastebin.com/{post['key']}"
        embed = discord.Embed(description=f"**{url}**", color=0x36393E)
        embed.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
        await ctx.send(embed=embed)

    @commands.command(aliases=['yn'])
    async def yesno(self, ctx, *, option: SafeConverter):
        """Yes or No"""
        reactions = ['✅', '❌']

        e = discord.Embed(description=option, color=0x36393E)
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")

        msg = await ctx.send(embed=e)

        for r in reactions:
            await msg.add_reaction(r)

    @commands.command(aliases=['same_tag'])
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def sametag(self, ctx, search_tag=None):
        search_tag = search_tag or ctx.author.discriminator
        users = [discord.utils.get(ctx.guild.members, discriminator=search_tag)]
        if not users:
            return await ctx.send(ctx.lang['not_found'])
        z = ',\n'.join([str(user) for user in users])
        await ctx.send(f"`{z}`")

    @commands.command()
    async def poll(self, ctx, *options: SafeConverter):
        """Tworzy głosowanie z max 10 opcjami."""
        if not options:
            return commands.UserInputError()
        if len(options) == 1:
            return await ctx.invoke(self.bot.get_command("yn"), option=''.join(options))
        elif len(options) <= 10:
            i = len(options)
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
            reactions = [numbers[c] for c in range(i)]
            msg = [f"{index + 1}. {options[index]}" for index, _ in enumerate(options)]
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
            async with self.bot.session.get(f'{page}/objects.inv') as resp:
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
            return (tup[0], tup[1], key(tup[2])) if key else tup

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
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rtfm(self, ctx, *, obj: str = None):
        await self.do_rtfm(ctx, 'latest', obj)

    @rtfm.command(name='python', aliases=['py'])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def rtfm_python(self, ctx, *, obj: str = None):
        await self.do_rtfm(ctx, 'python', obj)

    @commands.command(name="rtfs", aliases=["rts", "readthesource", "readthefuckingsourcegoddamnit"])
    @commands.cooldown(1, 4, commands.BucketType.user)
    async def read_the_source(self, ctx, *, query: typing.Optional[str] = None):
        """Przeszukuje zródło discord.py."""
        if not query:
            return await ctx.send("https://github.com/Rapptz/discord.py")

        payload = {
            "search": query
        }
        async with self.bot.session as cs:
            async with cs.get("https://rtfs.eviee.host/dpy/v1", params=payload) as r:
                source = await r.json(content_type='application/json')

        thing = []

        i = 0
        for result in source["results"]:
            thing.append(
                f"[{result['path'].replace('/', '.')}.{result['module']}.{result['object']}]({result['url']})")
            if i >= 5:
                break
            i += 1

        if not thing:
            return await ctx.send(ctx.lang['nothing_found'])

        embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 62), title=_(ctx.lang, "Wyniki dla `{query}`").format(query=query),
                              description="\n".join(thing))

        await ctx.send(embed=embed)

    @commands.command()
    async def pypi(self, ctx, name: str):
        """Szuka modułu z pypi.org."""
        if not name:
            return await ctx.send("https://pypi.org")
        async with ctx.typing():
            raw_html = self.bot.cogs['Fun'].simple_get(f"https://pypi.org/search/?q={name}")
            html = BeautifulSoup(raw_html, 'html.parser')
            name_s = html.find('span', attrs={'class': 'package-snippet__name'})
            ver = html.find('span', attrs={'class': 'package-snippet__version'})
            desc = html.find('p', attrs={'class': 'package-snippet__description'})

            e = discord.Embed(
                title=f"{name_s.text} v{ver.text}", description=desc.text, url=f"https://pypi.org/project/{name_s.text}")
            await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Useful(bot))
