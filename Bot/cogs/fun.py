import asyncio
import io
import random
import textwrap
import time
import unicodedata
import urllib
from functools import partial

import aiogtts
import aiohttp

import async_cleverbot as ac
import discord
import pyqrcode
import typing

from discord.ext import commands
from discord.ext.commands import BucketType

from . import utils
from .classes.converters import EmojiConverter, UrlConverter
from .music import Player
from .utils import get, get_language
from .utils.improved_discord import clean_text
from .classes.other import Plugin, SeleniumPhase
from pyfiglet import Figlet
from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup

from PIL import Image

from jishaku.functools import executor_function


class Fun(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        if not self.bot.development:
            self.cleverbot = ac.Cleverbot(get("cleverbot_api"))
            self.cleverbot.set_context(ac.DictContext(self.cleverbot))

        self.calls = dict()

        dank_memer_token = utils.get("dank_token")
        self.dank_headers = {
            'Authorization': dank_memer_token
        }

    @commands.command(aliases=['lyrics'])
    async def lyric(self, ctx, *, query: str = None):
        """Zwraca tekst danej piosenki."""
        if not query:
            player = self.bot.wavelink.get_player(ctx.guild.id, cls=Player)

            if not ctx.author.voice:
                await ctx.send(ctx.lang['am_not_on_any_vc'])
                return await ctx.add_react(False)

            elif not ctx.guild.me.voice:
                raise commands.UserInputError()

            elif ctx.guild.me.voice.channel != ctx.author.voice.channel:
                await ctx.send(ctx.lang['arent_with_me_on_vc'])
                return await ctx.add_react(False)

            elif not player.current:
                await ctx.send(ctx.lang['nothing_plays'])
                return await ctx.add_react(False)

            elif player.current:
                query = player.current.title
            else:
                raise commands.UserInputError()


        ksoft_token = utils.get("ksoft_token")
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

        if not r['data']:
            return await ctx.send(ctx.lang['nothing_found'])

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

    @executor_function
    def color_processing(self, color: discord.Color):
        with Image.new('RGB', (64, 64), color.to_rgb()) as im:
            buff = io.BytesIO()
            im.save(buff, 'png')
        buff.seek(0)
        return buff

    @commands.command()
    async def color(self, ctx, color: discord.Color = None):
        color = color or ctx.author.color
        buff = await self.color_processing(color=color)
        await ctx.send(file=discord.File(fp=buff, filename='color.png'))

    @commands.command(aliases=['fw', 'fullwidth', 'ａｅｓｔｈｅｔｉｃ'])
    async def aesthetic(self, ctx, *, msg):
        fullwidth_offset = 65248
        await ctx.send("".join(map(
            lambda c: chr(
                ord(c) + fullwidth_offset) if (0x21 <= ord(c) <= 0x7E) else c, msg)).replace(" ", chr(0x3000)))

    @commands.command()
    async def claps(self, ctx, *, text):
        i = 1
        p = []
        for _ in text:
            i += 1
            if i % 2:
                p.append(_.upper())
            else:
                p.append(_.lower())
        p = ''.join(p)
        _str = p.split()
        claps = '\U0001f44f'.join([i for i in _str])
        await ctx.send(claps)

    @commands.group(invoke_without_command=True)
    async def random(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @random.command()
    async def lenny(self, ctx):
        lenny = random.choice([
            "( ͡° ͜ʖ ͡°)", "( ͠° ͟ʖ ͡°)", "ᕦ( ͡° ͜ʖ ͡°)ᕤ", "( ͡~ ͜ʖ ͡°)",
            "( ͡o ͜ʖ ͡o)", "͡(° ͜ʖ ͡ -)", "( ͡͡ ° ͜ ʖ ͡ °)﻿", "(ง ͠° ͟ل͜ ͡°)ง",
            "ヽ༼ຈل͜ຈ༽ﾉ"
        ])
        await ctx.send(lenny)

    @commands.command(aliases=['choice'])
    async def choose(self, ctx, *choices: commands.clean_content):
        if len(choices) < 2:
            return await ctx.send(ctx.lang['err_choice_range'])

        await ctx.send(random.choice(choices))

    @commands.command()
    async def shrug(self, ctx):
        await ctx.send("¯\_(ツ)_/¯")

    def simple_get(self, url):
        try:
            with closing(get(url, stream=True)) as resp:
                if self.is_good_response(resp):
                    return resp.content
                else:
                    return None

        except RequestException as e:
            print('Error during requests to {0} : {1}'.format(url, str(e)))
            return None

    @staticmethod
    def is_good_response(resp):
        content_type = resp.headers['Content-Type'].lower()
        return (resp.status_code == 200
                and content_type is not None
                and content_type.find('html') > -1)

    @commands.command()
    async def yafud(self, ctx):
        raw_html = self.simple_get(f'http://www.yafud.pl/losowe/')
        html = BeautifulSoup(raw_html, 'html.parser')
        qt = html.find('span', attrs={'class': 'wpis-tresc'})
        qtrating = html.find('div', attrs={'class': 'wpis-box rating'})
        text = qt.text.replace(qtrating.text, "")

        discrim = html.find('span', attrs={"class": "fn"})
        tag = discrim.text
        bash = tag.replace("#", "")

        comp = f"ilosc_ocen-{bash}"
        pkt = html.find('span', attrs={"id": comp})
        punkty = pkt.text
        points = punkty.replace("Głosy: ", "")

        p = commands.Paginator()

        text = textwrap.wrap(text, 130)

        for line in text:
            p.add_line(line)

        p.add_line('\n')
        p.add_line(f'+{points} - yafud.pl/{bash}')

        for page in p.pages:
            await ctx.send(page)

    @commands.command()
    async def irc(self, ctx):
        raw_html = self.simple_get(f'http://bash.org/?random')
        html = BeautifulSoup(raw_html, 'html.parser')
        qt = html.find('p', attrs={'class': 'qt'})
        text = qt.text

        discrim = html.find('a', attrs={"title": "Permanent link to this quote."})
        tag = discrim.text
        bash = tag.replace("#", "?")

        z = f"```{text}\n\n> bash.org/{bash}```"
        await ctx.send(z)

    @commands.command()
    async def ascii(self, ctx, *, text):
        custom = Figlet()
        ascii_ = custom.renderText(text)
        await ctx.send(f"```{ascii_}```")

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, ctx.lang['not_found'])
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        await ctx.send(msg)

    @commands.command()
    @commands.cooldown(1, 30, BucketType.channel)
    async def who(self, ctx):
        try:
            member = random.choice(list(m.author for m in self.bot._connection._messages if m.guild == ctx.guild))
            e = discord.Embed(title=ctx.lang['who_is_that'], color=3553598)
            e.set_image(url=member.avatar_url)
            await ctx.send(embed=e)

            def check(m):
                return m.channel == ctx.channel and m.content == member.name or \
                       m.content.lower() == member.name.lower() or m.content == member.mention or \
                       m.content.lower() == member.display_name.lower()

            msg = await self.bot.wait_for('message', check=check, timeout=30)
            await ctx.send(f"{msg.author.mention}, {ctx.lang['it_was']} {member}.")

        except asyncio.TimeoutError:
            await ctx.send(ctx.lang['no_one_guessed'])

    @commands.command()
    @commands.is_nsfw()
    async def ss(self, ctx, *, page):
        async with ctx.typing():
            if not page.startswith("http"):
                page = f"https://{page}"
            if not page.endswith("/"):
                page = f"{page}/"

            start = time.time()
            try:
                im = await SeleniumPhase(self.bot).take_screenshot(page)
            except Exception:
                return await ctx.send(ctx.lang['could_not_take_ss'])

            if not im:
                return await ctx.send(ctx.lang['could_not_take_ss'])
            buffer = io.BytesIO()
            im.save(buffer, "png")
            buffer.seek(0)
        end = time.time()

        f = discord.File(fp=buffer, filename=f"ss.png")
        e = discord.Embed(title=page, color=3553598, timestamp=ctx.message.created_at)
        e.set_image(url=f"attachment://ss.png")
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
        await ctx.send(content=f"Done in {round(end-start)}s.", file=f, embed=e)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        query = f"{self.bot.user.mention} tell me "
        if message.content.lower().startswith(query):
            m = message.content.replace(query, "")

            group_commands = ['something ', 'what is ']

            if m.lower().startswith(group_commands[0]):
                m = m.replace(group_commands[0], "")

                allowed_subcommands = ['interesting', 'fun']

                if m not in allowed_subcommands:
                    return

                text = await self._invoke(message, m)

                return await message.channel.send(text)

            elif m.lower().startswith(group_commands[1]):
                m = m.replace(group_commands[1], "")

                allowed_subcommands = ['love']

                if m not in allowed_subcommands:
                    return

                text = await self._invoke(message, m)

                return await message.channel.send(text)

    async def _invoke(self, message, command):
        if not message.guild:
            lang = "eng"
        else:
            fetch = await self.bot.get_guild_settings(message.guild.id)
            lang = fetch.lang.lower()

        try:
            text = getattr(self, command)(lang)
        except Exception as e:
            return e
        return text

    @staticmethod
    def interesting(lang):
        if lang == "eng":
            facts = ['hello im dumb',
                     'hello im brilliand']

        elif lang == "pl":
            facts = ['siema jestem debilem',
                     'siema jestem mondry']

        else:
            raise NotImplemented(f"This language - {lang}, is not implemented")

        return random.choice(facts)

    @staticmethod
    def love(lang):
        if lang == "eng":
            response = [
                'https://www.youtube.com/watch?v=yYfWqC10j2E',
                'an intense feeling of deep affection.',
                'something we don\'t have.'
            ]

        elif lang == "pl":
            response = [
                'coś czego nie posiadamy.',
                'intensywne uczucie głębokiego uzależnienia od drugiej osoby',
                'https://www.youtube.com/watch?v=yYfWqC10j2E',
            ]

        else:
            raise NotImplemented(f"This language - {lang}, is not implemented")

        return random.choice(response)

    @commands.command()
    async def nitro(self, ctx, *, rest):
        rest = rest.lower()
        found_emojis = [emoji for emoji in ctx.bot.emojis
                        if emoji.name.lower() == rest and emoji.require_colons]
        if found_emojis:
            await ctx.send(str(random.choice(found_emojis)))
        else:
            await ctx.send(ctx.lang['not_found'])

    @commands.command(aliases=['google', 'g'])
    async def lmgtfy(self, ctx, *, query):
        await ctx.send("{}{}".format(
            random.choice(["https://google.com/search?q=", "https://lmgtfy.com/?q="]),
            urllib.parse.quote_plus(query)))

    @commands.command()
    async def ascii(self, ctx, *, text):
        custom = Figlet()
        ascii_ = custom.renderText(text)
        await ctx.send(f"```{ascii_}```")

    @staticmethod
    def processing(url) -> io.BytesIO:
        final_buffer = io.BytesIO()
        url.png(final_buffer, scale=10)

        final_buffer.seek(0)
        return final_buffer

    @commands.command(aliases=['qr'])
    async def qrcode(self, ctx, *, url: str):
        url = pyqrcode.create(url)

        fn = partial(self.processing, url)
        final_buffer = await self.bot.loop.run_in_executor(None, fn)
        file = discord.File(filename=f"{ctx.author.id}.png", fp=final_buffer)
        e = discord.Embed()
        e.set_image(url=f"attachment://{ctx.author.id}.png")
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
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
        text = f"{ctx.lang['howdy_sheriff']} {emote}."
        await ctx.send(template.replace(":emote:", str(emote)) + "\n" + text)

    @commands.command(name="10s")
    @commands.cooldown(1, 12, commands.BucketType.user)
    async def clickintenseconds(self, ctx):

        e = discord.Embed(title=ctx.lang['click_when_you_think'], description=ctx.lang['clicked_in'].format('?.??'))
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
        msg = await ctx.send(embed=e)
        await msg.add_reaction("\U000023f2")

        start = time.time()

        def ch(r, u):
            return r.message.channel == ctx.channel and u == ctx.author and str(r.emoji) == "\U000023f2"

        r, u = await self.bot.wait_for('reaction_add', check=ch)

        end = time.time()
        time_ = end - start

        e.description = ctx.lang['clicked_in'].format(round(time_, 2))
        await msg.edit(embed=e)

    @commands.command()
    async def tts(self, ctx, *, text: commands.clean_content):
        """Zwraca plik głosowy z twoją wiadomością."""
        async with ctx.typing():
            fp = io.BytesIO()
            lang = await get_language(self.bot, ctx.guild)

            if lang == "ENG":
                lang = "EN"

            await aiogtts.aiogTTS().write_to_fp(text, fp, lang=lang.lower())
            fp.seek(0)

        await ctx.send(file=discord.File(fp, filename=f"{ctx.author.id}.mp3"))

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

    @commands.command()
    async def nitro(self, ctx, *, rest):
        """Wysyła pierwszą znalezioną emotke z podaną nazwą."""
        rest = rest.lower()
        found_emojis = [emoji for emoji in ctx.bot.emojis
                        if emoji.name.lower() == rest and emoji.require_colons]
        if found_emojis:
            await ctx.send(str(random.choice(found_emojis)))
        else:
            await ctx.send(ctx.lang['nothing_found'])

    @commands.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def call(self, ctx):
        if ctx.author.id in self.calls:
            return await ctx.send(ctx.lang['already_in_call'])

        self.calls[ctx.author.id] = {"talking_with": None, "me": ctx.author, "channel": ctx.channel}

        await ctx.send(ctx.lang['added_to_call_queue'])

        for m in self.calls:
            if self.calls[m]['talking_with']:
                continue

            if m == ctx.author.id:
                continue

            if self.calls[m]['channel'] == ctx.channel:
                continue

            self.calls[m]['talking_with'] = ctx.author
            self.calls[ctx.author.id]['talking_with'] = self.calls[m]['me']
            await ctx.send(ctx.lang['found_caller'])
            break
        else:
            await ctx.send(ctx.lang['no_one_found_wait'])

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id not in self.calls:
            return

        if not self.calls[message.author.id]['talking_with']:  # nie ma drugiej osoby
            return

        talking_with = self.calls[message.author.id]['talking_with']

        if message.channel != self.calls[message.author.id]['channel']:
            return

        if message.content.lower() == "end":
            self.calls[talking_with.id]['talking_with'] = None
            del self.calls[message.author.id]

        channel = self.calls[talking_with.id]['channel']

        await channel.send(f"{message.author} >> {clean_text(message.content)}")
        await message.channel.send(f"{message.author} << {clean_text(message.content)}")

    @commands.command()
    async def bed(self, ctx, url: UrlConverter = None, url2: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            url2 = url2 or str(ctx.guild.me.avatar_url)
            params = {
                'avatar1': url,
                'avatar2': url2
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/bed", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def hitler(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/hitler", headers=self.dank_headers,
                                  params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    @commands.guild_only()
    async def guild_stats(self, ctx):
        messages, commands = await self.bot.db.fetchrow("SELECT messages, commands FROM count WHERE guild_id = $1",
                                                        ctx.guild.id)
        if not (messages and commands):
            return await ctx.send("this guild isnt listed.")

        await ctx.send(f"commands: **{commands}**\nmessages: **{messages}**.")  # todo make this better

    @commands.command()
    async def communism(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/communism", headers=self.dank_headers,
                                  params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def gay(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/gay", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def jail(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/jail", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def dab(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/dab", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def brazzers(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/brazzers", headers=self.dank_headers,
                                  params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def bongocat(self, ctx, url: UrlConverter = None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/bongocat", headers=self.dank_headers,
                                  params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)


def setup(bot):
    bot.add_cog(Fun(bot))
