import asyncio
import io
import random
import textwrap
import time
import unicodedata
import urllib
from functools import partial

import aiohttp

import async_cleverbot as ac
import discord
import pyqrcode

from discord.ext import commands

from .classes.converters import EmojiConverter
from .utils import get
from .classes.other import Plugin, SeleniumPhase
from pyfiglet import Figlet
from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup


class Fun(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        if not self.bot.development:
            self.cleverbot = ac.Cleverbot(get("cleverbot_api"))
            self.cleverbot.set_context(ac.DictContext(self.cleverbot))

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

    @commands.group(invoke_without_command=False)
    async def random(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(f"Incorrect random subcommand passed. Try {ctx.prefix}help random")

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
    async def who(self, ctx):
        try:
            member = random.choice(list(m.author for m in self.bot._connection._messages if m.guild == ctx.guild))
            e = discord.Embed(title=ctx.lang['who_is_that'], color=3553598)
            e.set_image(url=member.avatar_url)
            await ctx.send(embed=e)

            def check(m):
                return m.channel == ctx.channel and m.content == member.name or m.content.lower() == member.name.lower() or m.content == member.mention

            r = await self.bot.wait_for('message', check=check, timeout=15)
            await ctx.send(f"{r.author.mention}, {ctx.lang['it_was']} {member}.")

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
            await ctx.send(_(ctx.lang, "Nic nie znaleziono."))

    @commands.command(aliases=['google', 'lmgtfy'])
    async def g(self, ctx, *, query):
        await ctx.send("{}{}".format(
            random.choice(["https://google.com/search?q=", "https://lmgtfy.com/?q="]),
            urllib.parse.quote_plus(query)))

    @commands.command()
    async def ascii(self, ctx, *, text):
        custom = Figlet()
        ascii = custom.renderText(text)
        await ctx.send(f"```{ascii}```")

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
        await ctx.send(template.replace(":emote:", emote) + "\n" + text)


def setup(bot):
    bot.add_cog(Fun(bot))
