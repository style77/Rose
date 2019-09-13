import textwrap

import discord
from discord.ext import commands, tasks

import inspect
import os
import typing
import aiohttp
import asyncio
import dbl
import io
import aiogtts
import zlib
import urllib
import re
import random
import pyqrcode

from .utils import utils
from contextlib import closing
from functools import partial
from bs4 import BeautifulSoup
from requests import get
from requests.exceptions import RequestException
from datetime import datetime
from .classes.converters import EmojiConverter, SafeConverter

link_regex = re.compile(
    r"((http(s)?(\:\/\/))+(www\.)?([\w\-\.\/])*(\.[a-zA-Z]{2,3}\/?))[^\s\b\n|]*[^.,;:\?\!\@\^\$ -]")

def simple_get(url):
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                return None
    except RequestException as e:
        print(f'Wystąpił problem podczas zdobywania informacji o {url} : {e}')
        return None


def is_good_response(resp):
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200
            and content_type is not None
            and content_type.find('html') > -1)


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class Additional(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.token = utils.get_from_config("dbl")
        self.dblpy = dbl.Client(self.bot, self.token)
        if not self.bot.development:
            self.bot.loop.create_task(self.update_stats())
        if not self.bot.development:
            self.on_member_state_update.start()
        self.bot.session = aiohttp.ClientSession(loop=bot.loop)
        self.cd_mapping = commands.CooldownMapping.from_cooldown(
            1, 8, commands.BucketType.member)
        self.snipe = {}

    @commands.command()
    async def nitro(self, ctx, *, rest):
        """Wysyła pierwszą znalezioną emotke z podaną nazwą."""
        rest = rest.lower()
        found_emojis = [emoji for emoji in ctx.bot.emojis
                        if emoji.name.lower() == rest and emoji.require_colons]
        if found_emojis:
            await ctx.send(str(random.choice(found_emojis)))
        else:
            await ctx.send(_(ctx.lang, "Nic nie znaleziono."))

    # ksoft.si

    @commands.command(aliases=['lyrics'])
    async def lyric(self, ctx, *, query):
        """Zwraca tekst danej piosenki."""
        ksoft_token = utils.get_from_config("ksoft_token")
        url = "https://api.ksoft.si/lyrics/search"
        headers = {
            'Authorization': "Bearer " + ksoft_token
        }
        params = {
            'q': query
        }
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url, headers=headers, params=params) as r:
                r = await r.json()

        lyric_split = textwrap.wrap(r['data'][0]['lyrics'], 2000, replace_whitespace=False)
        embeds = []

        e = discord.Embed(
            title=f"{r['data'][0]['artist']} - {r['data'][0]['name']}", description=lyric_split.pop(0))
        embeds.append(e)

        for desc in lyric_split:
            embed = discord.Embed(description=desc)
            embeds.append(embed)

        for em in embeds:
            await ctx.send(embed=em)

    @commands.command(aliases=['google', 'lmgtfy'])
    async def g(self, ctx, *, query):
        await ctx.send("{}{}".format(
            random.choice(["https://google.com/search?q=", "https://lmgtfy.com/?q="]),
            urllib.parse.quote_plus(query)))

    #@commands.Cog.listener()
    #async def on_message(self, message):
        #if message.content.isdigit() and message.content == "1":
            #n = 1
            #while True:
                #if n == 3:
                    #await message.channel.send(_(await get_lang(self.bot, message.guild.id), "Rozpoczeliscie liczydełko!\nNastępną wiadomością musi być liczba o 1 wieksza."))
                #def check(m): return m.channel == message.channel and m.author != message.author and m.author.id != self.bot.user.id
                #msg = await self.bot.wait_for('message', check=check)
                #if not msg.content.isdigit() or int(msg.content) != n + 1:
                    #return await message.channel.send(f"Koniec wasz wynik **{n}**")
                #n += 1

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return

        self.snipe[message.guild.id] = {}
        self.snipe[message.guild.id]['content'] = message.content
        self.snipe[message.guild.id]['author'] = message.author
        self.snipe[message.guild.id]['timestamp'] = message.created_at

    @commands.command(name="snipe")
    async def snipe_(self, ctx):
        """Sprawdź ostatnią usuniętą wiadomość."""
        if ctx.guild.id not in self.snipe:
            return await ctx.send(_(ctx.lang, "Nie udało mi się zarejstrować żadnej usuniętej wiadomości."))
        e = discord.Embed(
            description=self.snipe[ctx.guild.id]['content'], timestamp=self.snipe[ctx.guild.id]['timestamp'])
        e.set_author(name=self.snipe[ctx.guild.id]['author'].name,
                     icon_url=self.snipe[ctx.guild.id]['author'].avatar_url)
        return await ctx.send(embed=e)

    def parse_object_inv(self, stream, url):
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
            sub = cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError(
                        'Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache


    def finder(self, text, collection, *, key=None, lazy=True):
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

        def transform(tup):
            return tup[0]

        matches = self.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

        e = discord.Embed()
        if len(matches) == 0:
            return await ctx.send(_(ctx.lang, "Niczego nie znaleziono."))

        e.description = '\n'.join(f'[{key}]({url})' for key, url in matches)
        await ctx.send(embed=e)

    @commands.group(aliases=['rtfd'], invoke_without_command=True)
    async def rtfm(self, ctx, *, obj: str = None):
        """Szuka podanego obiektu w dokumentacji discord.py."""
        await self.do_rtfm(ctx, 'latest', obj)

    @rtfm.command(name='python', aliases=['py'])
    async def rtfm_python(self, ctx, *, obj: str = None):
        """Szuka podanego obiektu w dokumentacji pythona."""
        await self.do_rtfm(ctx, 'python', obj)

    @commands.command(hidden=True)
    async def source(self, ctx, *, command: str = None):
        """Zwraca link do źródła komendy."""
        source_url = 'https://github.com/Style77/Rose'
        if command is None:
            return await ctx.send(source_url)

        obj = self.bot.get_command(command.replace('.', ' '))
        if obj is None:
            return await ctx.send(_(ctx.lang, 'Nie znaleziono komendy.'))

        src = obj.callback.__code__
        lines, firstlineno = inspect.getsourcelines(src)
        if not obj.callback.__module__.startswith('discord'):
            location = os.path.relpath(src.co_filename).replace('\\', '/')
            final_url = f'<{source_url}/blob/master/Bot/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        else:
            location = obj.callback.__module__.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            final_url = f'<{source_url}/blob/rewrite/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        await ctx.send(final_url)

    @commands.command(name="rtfs", aliases=["rts", "readthesource", "readthefuckingsourcegoddamnit"])
    @commands.cooldown(1, 2.5, commands.BucketType.user)
    async def read_the_source(self, ctx, *, query: typing.Optional[str] = None):
        """Przeszukuje zródło discord.py."""
        if not query:
            return await ctx.send("https://github.com/Rapptz/discord.py")

        payload = {
            "search": query
        }
        async with aiohttp.ClientSession() as cs:
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
            return await ctx.send(_(ctx.lang, "Brak wyników."))

        embed = discord.Embed(colour=discord.Colour.from_rgb(54, 57, 62), title=_(ctx.lang, "Wyniki dla `{query}`").format(query=query),
                              description="\n".join(thing))

        await ctx.send(embed=embed)

    @commands.command()
    async def pypi(self, ctx, name: str):
        """Szuka modułu z pypi.org."""
        if not name:
            return await ctx.send("https://pypi.org")
        async with ctx.typing():
            raw_html = simple_get(f"https://pypi.org/search/?q={name}")
            html = BeautifulSoup(raw_html, 'html.parser')
            name_s = html.find('span', attrs={'class': 'package-snippet__name'})
            ver = html.find('span', attrs={'class': 'package-snippet__version'})
            desc = html.find('p', attrs={'class': 'package-snippet__description'})

            e = discord.Embed(
                title=f"{name_s.text} v{ver.text}", description=desc.text, url=f"https://pypi.org/project/{name_s.text}")
            await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.content != before.content:
            ctx = await self.bot.get_context(after)
            if ctx.valid:
                bucket = self.cd_mapping.get_bucket(after)
                retry_after = bucket.update_rate_limit()
                if retry_after:
                    seconds = retry_after
                    seconds = round(seconds, 2)
                    hours, remainder = divmod(int(seconds), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    now = datetime.utcnow()
                    time = datetime(now.year, now.month, now.day,
                                minute=minutes, second=seconds)
                    time = time.strftime("%H:%M:%S")

                    return await after.channel.send(
                        _(await get_language(self.bot, after.guild.id), "Poczekaj jeszcze {time}.").format(time=time))
                try:
                    await self.bot.process_commands(after)
                except commands.CommandNotFound:
                    return

    def processing(self, url) -> io.BytesIO:
        final_buffer = io.BytesIO()
        url.png(final_buffer, scale=10)

        final_buffer.seek(0)
        return final_buffer

    @commands.command(aliases=['qr'])
    async def qrcode(self, ctx, *, url: str):
        url = pyqrcode.create(url)
        
        fn = partial(self.processing, url)
        final_buffer = await self.bot.loop.run_in_executor(None, fn)
        file = discord.File(filename=f"siema.png", fp=final_buffer)
        e = discord.Embed()
        e.set_image(url="attachment://siema.png")
        e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
        await ctx.send(file=file, embed=e)

    @commands.command(aliases=['sherif'])
    async def sheriff(self, ctx, emote: EmojiConverter):
        """Zwraca szeryfa z podanej emotki."""
        template = """
            ⠀ ⠀ ⠀     :cowboy:
    　   :emote::emote::emote:
        :emote:   :emote:　:emote:
    :point_down:   :emote::emote: :point_down:
    　  :emote:　:emote:
    　   :emote:　 :emote:
    　   :boot:     :boot:
        """
        text = _(ctx.lang, "cześć. Jestem szeryfem {}.").format(emote)
        await ctx.send(template.replace(":emote:", emote) + "\n" + text)

    @commands.command(aliases=['yn'])
    async def yesno(self, ctx, *, option: SafeConverter):
        """YesNo"""
        reactions = ['✅', '❌']
        msg = f"{option}"
        msg = await ctx.send(msg)
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
                c+=1
            index = 0
            msg = []
            for opt in options:
                msg.append(f"{index+1}. {options[index]}")
                index += 1
            msg = '\n'.join(msg)
        else:
            return await ctx.send(_(ctx.lang, "Możesz ustawić najwięcej 10 opcji."))
        msg = await ctx.send(msg)
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

    async def update_stats(self):
        await self.bot.wait_until_ready()
        while True:
            try:
                await self.dblpy.post_server_count()
            except Exception as e:
                print(e)
            await asyncio.sleep(180)

    @commands.Cog.listener()
    async def on_message(self, m):
        member = await self.bot.pg_con.fetchrow("SELECT * FROM members WHERE id = $1", m.author.id)
        if not member:
            return
        await self.bot.pg_con.execute("UPDATE members SET all_messages = $1 WHERE id = $2", member['all_messages'] + 1, m.author.id)

    @tasks.loop(seconds=1)
    async def on_member_state_update(self):
        try:
            members = await self.bot.pg_con.fetch("SELECT * FROM members")
            for member in members:
                g = min([guild for guild in self.bot.guilds if guild.get_member(
                    member['id'])], key=lambda guild: guild.id)
                if g:
                    m = g.get_member(member['id'])
                    await self.bot.pg_con.execute(f"UPDATE members SET {m.status} = $1 WHERE id = $2", member[str(m.status)]+1, m.id)
        except Exception as e:
            print(e)

    @on_member_state_update.before_loop
    async def b4(self):
        await self.bot.wait_until_ready()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def give_premium(self, ctx, member: discord.Member):
        """Daje premium danemu userowi.\n Tylko dla właściciela!
        """
        x = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", member.id)
        if not x:
            await self.bot.pg_con.execute("INSERT INTO members (id) VALUES ($1)", member.id)
        return await ctx.send(":ok_hand:")

    def cog_unload(self):
        self.on_member_state_update.cancel()

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if not member:
            return

        if not ctx.command.name in member[0]['commands']:
            member[0]['commands'].append(ctx.command.name)
            await self.bot.pg_con.execute("UPDATE members SET commands = $1 WHERE id = $2", member[0]['commands'], ctx.author.id)

    @commands.command()
    async def progress(self, ctx, member: discord.Member):
        """Pokazuje progres komend danej osoby."""
        m = member or ctx.author
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", m.id)
        if not member:
            return await ctx.send(_(ctx.lang, "{mention}, nie posiada konta premium.").format(mention=m.mention))

        i = 0
        for c in self.bot.walk_commands():
            i += 1
        z = "{0:.2f}".format((len(member[0]['commands'])/i)*100)
        return await ctx.send(f"Progress: **{z}%**")

    @commands.command()
    async def vote(self, ctx):
        """Dziękuje ❤"""
        return await ctx.send(_(ctx.lang, "Głosuj na Rose!\n<https://discordbots.org/bot/538369596621848577/vote>"))

    @commands.command()
    async def invite(self, ctx):
        """Dziękuje ❤"""
        return await ctx.send("<https://discordapp.com/oauth2/authorize?client_id=538369596621848577&scope=bot&permissions=8> ❤")

    @commands.command()
    async def support(self, ctx):
        """Dołącz, jeśli masz problem z botem."""
        return await ctx.send(_(ctx.lang, "Dołącz na serwer pomocy!\nhttps://discord.gg/EZ3TsYY"))

    @commands.command()
    async def docs(self, ctx):
        """Dokumentacja bota."""
        await ctx.send("<https://style77.github.io>")

    @commands.command()
    async def tts(self, ctx, *, text: commands.clean_content="gay"):
        """Zwraca plik głosowy z twoją wiadomością."""
        async with ctx.typing():
            fp = io.BytesIO()
            lang = str(ctx.lang).lower()
            if str(ctx.lang) == "ENG":
                lang = 'en'
            await aiogtts.aiogTTS().write_to_fp(text, fp, lang=lang)
            fp.seek(0)

        await ctx.send(file=discord.File(fp, filename="tts.mp3"))

    @commands.command(name="emoji", aliases=["bigemoji", "emojibig", "big_emoji"])
    async def big_emoji(self, ctx, emoji: typing.Union[discord.Emoji, discord.PartialEmoji, str]):
        """Duża wersja emotki."""
        if isinstance(emoji, (discord.Emoji, discord.PartialEmoji)):
            fp = io.BytesIO()
            await emoji.url.save(fp)

            e = discord.Embed()
            e.set_image(url=f"attachment://{emoji.name}{'.png' if not emoji.animated else '.gif'}")
            e.set_footer(text=f"Emoji from: {emoji.guild_id}")
            await ctx.send(file=discord.File(fp, filename=f"{emoji.name}{'.png' if not emoji.animated else '.gif'}"),
                           embed=e)
        else:
            fmt_name = "-".join(f"{ord(c):x}" for c in emoji)
            async with aiohttp.ClientSession() as cs:
                url = f"http://twemoji.maxcdn.com/2/72x72/{fmt_name}.png"
                r = await cs.get(url)

                e = discord.Embed()
                e.set_image(url=f"attachment://{fmt_name}.png")
                e.set_footer(text=f"URL: {url}")
                await ctx.send(
                    file=discord.File(io.BytesIO(await r.read()), filename=f"{fmt_name}.png"),
                    embed=e)

    @commands.command(name="firstmsg", aliases=["firstmessage", "first_message"])
    async def first_message(self, ctx, channel: discord.TextChannel = None):
        """Pierwsza wiadomość z danego kanału."""
        channel = channel or ctx.channel

        first_message = (await channel.history(limit=1, oldest_first=True).flatten())[0]

        embed = discord.Embed(title=f"#{channel}'s first message", description=first_message.content)
        embed.set_author(name=str(first_message.author), icon_url=first_message.author.avatar_url)
        embed.add_field(name="\u200b", value=f"[Jump!]({first_message.jump_url})")
        embed.set_footer(text=f"Message is from {first_message.created_at}")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Additional(bot))
