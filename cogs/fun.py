import discord
from discord.ext import commands
from discord.ext.commands.cooldowns import BucketType

import aiohttp
import colorsys
import random
import os
import time
import async_cleverbot as ac
import psutil
import urbandict
import urllib.request
import speedtest
import io
import typing
import asyncio
import unicodedata
import wrapper
import math
import textwrap

from cogs.utils import utils
from io import BytesIO
from googletrans import Translator
from pyfiglet import Figlet
from datetime import timedelta, datetime
from requests import get
from requests.exceptions import RequestException
from contextlib import closing
from bs4 import BeautifulSoup
from PIL import Image
from functools import partial
from typing import Union
from cogs.classes.converters import urlConverter

def simple_get(url):
    try:
        with closing(get(url, stream=True)) as resp:
            if is_good_response(resp):
                return resp.content
            else:
                return None

    except RequestException as e:
        print('Error during requests to {0} : {1}'.format(url, str(e)))
        return None

def is_good_response(resp):
    content_type = resp.headers['Content-Type'].lower()
    return (resp.status_code == 200
            and content_type is not None
            and content_type.find('html') > -1)

def uptime():
    p = psutil.Process(os.getpid())
    return int(time.time() - p.create_time())

class Fun(commands.Cog):
    def __init__(self,bot):
        self.bot = bot
        self.translator = Translator()
        self.cleverbot = ac.Cleverbot(utils.get_from_config("cleverbot_api"))
        self.cleverbot.set_context(ac.DictContext(self.cleverbot))
        self.session = aiohttp.ClientSession(loop=bot.loop)

    @commands.command(aliases=['fw', 'fullwidth', 'ａｅｓｔｈｅｔｉｃ'])
    async def aesthetic(self, ctx, *, msg: str="iam gay"):
        """ａｅｓｔｈｅｔｉｃ"""
        FULLWIDTH_OFFSET = 65248
        await ctx.send("".join(map(
            lambda c: chr(ord(c) + FULLWIDTH_OFFSET) if (ord(c)
                                                         >= 0x21 and ord(c) <= 0x7E) else c,
            msg)).replace(" ", chr(0x3000)))

    @commands.command(aliases=["hb", "note"])
    async def hastebin(self, ctx, *, content):
        if not content:
            raise commands.UserInputError()
        async with aiohttp.ClientSession() as session:
            async with session.post("https://hastebin.com/documents", data=content.encode('utf-8')) as post:
                post = await post.json()
                url = f"https://hastebin.com/{post['key']}"
        await ctx.send(url)

    @commands.command()
    async def meme(self, ctx, number: int=None):
        async with aiohttp.ClientSession() as session:
            if not number:
                async with session.get("http://style7.pythonanywhere.com/api/v1.0/random_meme") as resp:
                    response = await resp.json()
            elif await self.bot.is_owner(ctx.author) and number:
                async with session.get(f"http://style7.pythonanywhere.com/api/v1.0/memes/{number}") as resp:
                    response = await resp.json()
        dyz = await self.bot.fetch_user(411950980087939073)
        e = discord.Embed(color=3553598)
        e.set_footer(text=f'{dyz.name}', icon_url=dyz.avatar_url)
        try:
            e.set_image(url=response['memes']['url'])
        except KeyError:
            return await ctx.send(_(ctx.lang, "Nie ma mema o takim numerze w bazie."))
        await ctx.send(embed=e)

    @commands.command()
    @commands.is_nsfw()
    async def swear(self, ctx, *, scentence):
        """Jeśli nie masz pomysłu na wyzwiska :DDD"""
        new = ''
        newsplitted = []
        splitted = scentence.split(' ')
        lang = ctx.lang
        if lang == "ENG":
            words = ['bitch', 'motherfucker', 'gay', 'lesbian', 'fucker', 'boi', 'faggot', 'goddamn']
            end_words = [', okay bitch?!', ', now shut up', ', sit down boi']
        else:
            words = ['suka ', 'jebacz matek ', 'gej ', 'lesba ', 'kurwa ', "pedau "]
            end_words = [', okej suko?!', ', teraz zamknij morde', ', wypierdalaj']
        for x in splitted:
            newsplitted.append(x)
            if random.randint(0, 1):
                newsplitted.append(random.choice(words))
            for x in ' '.join(newsplitted):
                if random.randint(0, 1):
                    new += x.upper()
                else:
                    new += x.lower()
            if random.randint(0, 8) > 5:
                for x in random.choice(end_words):
                    if random.randint(0, 1):
                        new += x.upper()
                    else:
                        new += x.lower()
        await ctx.send(new)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def speedtest(self, ctx):
        async with ctx.channel.typing():
            s = speedtest.Speedtest()
            s.get_servers()
            s.get_best_server()
            s.download()
            s.upload()
            res = s.results.dict()
            down = round(res["download"]/1024/1024)
            up = round(res["upload"]/1024)
            ping = round(res["ping"])
            await ctx.send(f"```wyniki:\ndownload: {down}mb/s\nupload: {up}mb/s\nping: {ping}```")

    @commands.group(invoke_without_command=True)
    @commands.is_nsfw()
    async def search(self, ctx):
        await ctx.send(_(ctx.lang, '```youtube - szuka filmu z youtube-a\n```'))

    @search.command(aliases=['yt'])
    @commands.is_nsfw()
    async def youtube(self, ctx, *, queryy):
        """Szuka filmu z Youtube."""
        textToSearch = queryy
        query = urllib.parse.quote(textToSearch)
        url = "https://www.youtube.com/results?search_query=" + query
        response = urllib.request.urlopen(url)
        html = response.read()
        soup = BeautifulSoup(html, 'html.parser')
        vid = soup.find(attrs={'class':'yt-uix-tile-link'})
        await ctx.send('https://www.youtube.com' + vid['href'])

    @commands.command()
    async def claps(self, ctx, *, text=None):
        """D👏E👏S👏P👏A👏C👏I👏T👏O"""
        if not text:
            raise commands.UserInputError()
        i = 1
        p = []
        for _ in text:
            i += 1
            if i%2:
                p.append(_.upper())
            else:
                p.append(_.lower())
        p = ''.join(p)
        _str = p.split()
        claps = '\U0001f44f'.join([i for i in _str])
        await ctx.send(claps)

    @commands.command()
    async def yafud(self, ctx):
        """Mniej jakościowe historyjki po Polsku."""
        raw_html = simple_get(f'http://www.yafud.pl/losowe/')
        html = BeautifulSoup(raw_html, 'html.parser')
        qt = html.find('span', attrs={'class': 'wpis-tresc'})
        qtrating = html.find('div', attrs={'class': 'wpis-box rating'})
        text = qt.text.replace(qtrating.text,"")

        discrim = html.find('span', attrs={"class": "fn"})
        tag = discrim.text
        bash = tag.replace("#", "")

        comp = f"ilosc_ocen-{bash}"
        pkt = html.find('span', attrs={"id": comp})
        punkty = pkt.text
        points = punkty.replace("Głosy: ","")

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
        """Bardziej jakościowe historyjki po Angielsku."""
        raw_html = simple_get(f'http://bash.org/?random')
        html = BeautifulSoup(raw_html, 'html.parser')
        qt = html.find('p', attrs={'class': 'qt'})
        text = qt.text

        discrim = html.find('a', attrs={"title":"Permanent link to this quote."})
        tag = discrim.text
        bash = tag.replace("#", "?")

        z=f"```{text}\n\n> bash.org/{bash}```"
        await ctx.send(z)

    @commands.command()
    @commands.is_nsfw()
    async def define(self, ctx,*,text=None):
        """Definicja wyrazu z urbandictionary.com"""
        try:
            z = urbandict.define(text)
            nazwa = z[0]["word"]
            defi = z[0]["def"]
            example = z[0]["example"]
            await ctx.send(f"**{nazwa}**\n> {defi}\n\n      * {example}")
        except Exception:
            return await ctx.send(_(ctx.lang, "Nie znaleziono **{text}**.").format(text=text))

    @commands.command()
    async def ascii(self, ctx, *, text=None):
        if not text:
            raise commands.UserInputError()
        custom = Figlet()
        ascii = custom.renderText(text)
        await ctx.send(f"```{ascii}```")

    @commands.command()
    async def bombs(self, ctx, liczba: int):
        if liczba > 111:
            return await ctx.send(_(ctx.lang, "Liczba nie może być większa niż 111."))
        p = []
        for _ in range(liczba):
            x=random.randint(1,100)
            if x <= 20:
                z="||:bomb:||"
            else:
                if x >= 21 and x <= 60:
                    z="||0\N{combining enclosing keycap}||"
                elif x >= 61 and x <= 80:
                    z="||1\N{combining enclosing keycap}||"
                elif x >= 81 and x <= 100:
                    z="||2\N{combining enclosing keycap}||"
            p.append(z)
        await ctx.send("".join(p[:15])+"\n"+"".join(p[16:31])+"\n"+"".join(p[32:47])+"\n"+"".join(p[48:63])+"\n"+"".join(p[64:79])+"\n"+"".join(p[80:95])+"\n"+"".join(p[96:111]))

    @commands.command()
    async def charinfo(self, ctx, *, characters: str):
        """Pokazuje informacje o emotce, bądź literze."""

        lang = ctx.lang
        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, _(lang, "Nie znalazłem nic takiego."))
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'
        msg = '\n'.join(map(to_string, characters))
        #p = commands.Paginator(prefix='', suffix='')
        #for line in msg:
            #p.add_line(line)
        #for page in p.pages:
        await ctx.send(msg)

    @commands.command()
    async def who(self, ctx):
        try:
            member=random.choice(list(m.author for m in self.bot._connection._messages if m.guild == ctx.guild))
            e=discord.Embed(title=_(ctx.lang, "Kto to?"),color=3553598)
            e.set_image(url=member.avatar_url)
            await ctx.send(embed=e)

            def check(m):
                return m.channel == ctx.channel and m.content == member.name or m.content.lower() == member.name.lower() or m.content == member.mention

            r = await self.bot.wait_for('message', check=check, timeout=15)
            await ctx.send(_(ctx.lang, "{mention} tak to był {member}.").format(mention=r.author.mention, member=member))

        except asyncio.TimeoutError:
            await ctx.send(_(ctx.lang, "Niestety nikt nie zgadł na czas."))

    @commands.command(name='ss')
    @commands.is_nsfw()
    async def ss(self, ctx, page="https://google.com/"):
        if not page.startswith("https://"):
            page=f"https://{page}"
        if not page.endswith("/"):
            page=f"{page}/"
        e=discord.Embed(title=page,color=3553598,timestamp=ctx.message.created_at)
        e.set_image(url=f"https://api.apiflash.com/v1/urltoimage?access_key=eac65fa1e35b44bfb79c9bb570aa650f&url={page}")
        e.set_footer(text=ctx.author.name,icon_url=ctx.author.avatar_url)
        await ctx.send(embed=e)

    @ss.error
    async def ss_handler(self,ctx,error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(_(ctx.lang, "Ten kanał nie jest nsfw."))

    @commands.command(name="cleverbot", aliases=["cb"])
    @commands.cooldown(1, 2, commands.BucketType.user)
    async def cleverbot_(self, ctx, *, query: str):
        try:
            r = await self.cleverbot.ask(query, ctx.author.id)
        except ac.InvalidKey:
            return await ctx.send(_(ctx.lang, "Wystąpił problem z którym musicie zgłosić się do właściciela bota.\nError: InvalidKey"))
        except ac.APIDown:
            return await ctx.send(_(ctx.lang, "Musze czasami spać."))
        else:
            lang = ctx.lang
            if lang == "ENG":
                lang = "EN"
            trans = self.translator.translate(r.text, dest=lang.lower())
            await ctx.send(f"{trans.text}")

        def __unload(self):
            self.bot.loop.create_task(self.cleverbot.close())

    @commands.Cog.listener()
    async def on_command_completion(self,ctx):
        await self.bot.pg_con.execute("UPDATE bot_count SET commands = commands + 1")

        if not ctx.guild:
            return
        count = await self.bot.pg_con.fetch("SELECT * FROM count WHERE guild_id = $1", str(ctx.guild.id))
        if not count:
            return await self.bot.pg_con.execute("INSERT INTO count (guild_id) VALUES ($1)", str(ctx.guild.id))
        await self.bot.pg_con.execute("UPDATE count SET commands = $1 WHERE guild_id = $2", count[0]['commands']+1, str(ctx.guild.id))

    @commands.Cog.listener()
    async def on_message(self, message):
        await self.bot.pg_con.execute("UPDATE bot_count SET messages = messages + 1")

        if not message.guild:
            return

        if message.guild.id == 336642139381301249:
            return

        count = await self.bot.pg_con.fetch("SELECT * FROM count WHERE guild_id = $1", str(message.guild.id))
        if not count:
            return await self.bot.pg_con.execute("INSERT INTO count (guild_id) VALUES ($1)", str(message.guild.id))
        await self.bot.pg_con.execute("UPDATE count SET messages = $1 WHERE guild_id = $2", count[0]['messages']+1, str(message.guild.id))

        if message.guild.id == 538366293921759233:
            odzywki = {
                "despacito": "wszystko z toba dobrze?",
                "<@185712375628824577>": "https://cuck.host/SRLevrs.png",
                "kk": "Ile czasu zaoszczędziłeś tym skrótem?",
                "Xd": "ale beka Xddd",
                'kys': 'Sam sie zabij kurwo',
                ':)': "https://cuck.host/NNYkbyv.png",
                ':smiley:': "https://cuck.host/NNYkbyv.png",
                "jd": "Jebac disa kurwe zwisa syna szatana orka jebanego tibijskiego",
                "jebac disa": "tez tak mysle",
                "dobranoc": "smacznego",
                "ale beka": "no",
                "Ale beka": "No",
                "x": "kurwa\nd",
                "mam iphone": "ｓｏ  ｅｄｇｙ",
                "mam iphona": "ｓｏ  ｅｄｇｙ"
            }
            if message.content in odzywki:
                x = odzywki[message.content]
                await message.channel.send(x)
            if message.content.lower() == "ok":
                reacts = ["🇩","🇮","🇪"]
                for reaction in reacts:
                    await message.add_reaction(reaction)
            if message.content.lower() in ["twoj stary","twój stary","twuj stary"]:
                reacts = ["➕","1\N{combining enclosing keycap}"]
                for reaction in reacts:
                    await message.add_reaction(reaction)
            if message.content.lower() in ["koham cie","kocham cię","kocham cie","koham cię"]:
                reacts = ["🇯","🅰","🇨","🅱","🇹","🇪","🇿"]
                for reaction in reacts:
                    await message.add_reaction(reaction)

    @commands.command(name="kot", aliases=["koteł"])
    async def kot_(self, ctx):
        """🐱"""
        async with aiohttp.ClientSession() as session:
            async with session.get("http://aws.random.cat/meow") as resp:
                response = await resp.json()
        values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
        e = discord.Embed(color=discord.Color.from_rgb(*values))
        e.set_image(url=response["file"])
        await ctx.send(embed=e)

    @commands.command(aliases=["pies", "pieseł"])
    async def dog(self, ctx):
        """🐶"""
        async with aiohttp.ClientSession() as session:
            async with session.get("https://random.dog/woof.json") as resp:
                response = await resp.json()
        values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
        e = discord.Embed(color=discord.Color.from_rgb(*values))
        e.set_image(url=response["url"])
        await ctx.send(embed=e)

    @commands.command(sliases=["staty", "uptime"])
    async def stats(self, ctx):
        """Statystyki bota."""
        global_ = await self.bot.pg_con.fetch("SELECT * FROM bot_count")
        server_ = await self.bot.pg_con.fetch("SELECT * FROM count WHERE guild_id = $1", str(ctx.guild.id))
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if member:
            desc = _(ctx.lang, "**{}** wysłanych wiadomości ogółem\n**{}** wysłanych wiadomości na tym serwerze\n**{}** użytych komend ogółem\n**{}** użytych komend na tym serwerze.\n**{}** ogólnie wysłanych wiadomości przez ciebie.").format(global_[0]['messages'],
                                                    server_[0]['messages'],
                                                    global_[0]['commands'],
                                                    server_[0]['commands'],
                                                    member[0]['all_messages'])
        elif not member:
            desc = _(ctx.lang, "**{}** wysłanych wiadomości ogółem\n**{}** wysłanych wiadomości na tym serwerze\n**{}** użytych komend ogółem\n**{}** użytych komend na tym serwerze.").format(global_[0]['messages'],
                                                        server_[0]['messages'],
                                                        global_[0]['commands'],
                                                        server_[0]['commands'])
        e = discord.Embed(title=_(ctx.lang, "Od czasu mojego włączenia zarejestrowałem"),
                          description=desc, color=3553598)
        await ctx.send(embed=e)
        czas = str(timedelta(seconds=uptime()))
        e = discord.Embed(description=czas, color=3553598)
        await ctx.send(embed=e)

    @commands.command(hidden=True)
    @commands.is_owner()
    async def kuba_bans(self, ctx):
        """Nic ważnego."""
        if ctx.guild.id == 527150156324536321:
            global_ = await self.bot.pg_con.fetch("SELECT * FROM bot_count")
            return await ctx.send(_(ctx.lang, "Kuba dostał już **{}** banów od Bartka.").format(global_[0]['kuba_bans']))

    @commands.command(hidden=True)
    async def ping(self, ctx):
        """Do testowania, czy bot odpowiada."""
        await ctx.send(_(ctx.lang, "Mój ping to: {}.").format(round(self.bot.latency*1000)))

    @commands.command(aliases=["avy", "awatar"])
    async def avatar(self, ctx, member: discord.Member=None):
        """Zwraca awatar, twój bądź osoby oznaczonej."""
        member = member or ctx.author

        e = discord.Embed(color=member.color)
        e.set_image(url=member.avatar_url)
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
            description=user.name +
                ("<:bottag:597838054237011968>" if user.bot else ''),
            color = user.color,
            timestamp = ctx.message.created_at)
        userembed.set_author(
            name=user.display_name, icon_url=user.avatar_url)
        userembed.set_thumbnail(url=user.avatar_url)
        userembed.add_field(name=_(ctx.lang, "Dołączył do nas"), value=userjoinedat)
        userembed.add_field(name=_(ctx.lang, "Założył konto"), value=usercreatedat)
        if user.activity:
            userembed.add_field(name=_(ctx.lang, "Gra w"), value=user.activity.name)
        userembed.add_field(name=_(ctx.lang, "Wspólne serwery"), value=shared)
        if user.status is not None:
            userembed.add_field(name=_(ctx.lang, "Status"), value=user.status)
        userembed.add_field(name=_(ctx.lang, "Kolor rangi"), value=user.color)
        userembed.add_field(name=_(ctx.lang, "Tag"), value=f'`{user.discriminator}`')
        userembed.add_field(name=_(ctx.lang, "Najwyższa ranga"), value=str(user.top_role))
        userembed.set_footer(text=f'ID: {user.id}')
        await ctx.send(embed=userembed)

    @commands.command(hidden=True)
    @commands.cooldown(1, 10, BucketType.guild)
    async def cebulak(self, ctx, *, data):
        if ctx.guild.id != 538366293921759233:
            return
        async with aiohttp.ClientSession() as session:
            webhook = discord.Webhook.from_url('data:application/octet-stream;base64,eyJuYW1lIjogImNlYnVsYWN6ZWsiLCAiY2hhbm5lbF9pZCI6ICI1Mzg0MjQxMjIyMDQ3NDk4MzYiLCAidG9rZW4iOiAiN0xSLXAwbGo3T0RYTE02aHFUM2VuaERSUVp3RXY5eWpQR0JUT29IdGROQmkxUnVXRW1UaDJ4ZWpTeUdTRDRnZEw3WHoiLCAiYXZhdGFyIjogbnVsbCwgImd1aWxkX2lkIjogIjUzODM2NjI5MzkyMTc1OTIzMyIsICJpZCI6ICI1Mzg0MjU1Njc2OTE4MDA1OTEifQ==', adapter=discord.AsyncWebhookAdapter(session))
            e = discord.Embed(description=f"**{data}**", color=3553598, timestamp=ctx.message.created_at)
            if ctx.message.attachments:
                e.set_image(url=ctx.message.attachments[0].url)
            if ctx.author.avatar_url != "":
                await webhook.send(embed=e, username=ctx.author.name, avatar_url=ctx.author.avatar_url_as(format='png'))

    @commands.command(aliases=["amionmobile?", "jestemnatelefonie?", "jestemnatel?", "jestemnatel"])
    async def amionmobile(self, ctx, member: discord.Member=None):
        """Sprawdza czy jesteś na urządzeniu mobilnym."""
        member = member or ctx.author
        if member.is_on_mobile():
            await ctx.send(_(ctx.lang, "Tak."))
        else:
            await ctx.send(_(ctx.lang, "Nie."))

    #@commands.command()
    #async def translate(self, ctx, lg="pl", *, text=None):
        #"""Tłumaczy podany tekst."""
        #trans = self.translator.translate(text, dest=lg)
        #flaga1 = trans.src
        #flaga2 = lg
        #if (trans.src or lg) == "en":
            #flaga1 = "gb"
        #e = discord.Embed(title=_(ctx.lang, "Tłumaczenie z :flag_{flaga1}: na :flag_{flaga2}:").format(flaga1=flaga1, flaga2=flaga2), description=trans.text, color=3553598)
        #await ctx.send(embed=e)

    @commands.command()
    async def spotify(self, ctx, member: discord.Member=None):
        member = member or ctx.author

        if member.activity is not None and member.activity.type is discord.ActivityType.listening:
            z = (datetime.utcnow()-member.activity.start).seconds
            dur = member.activity.duration.seconds
            czas = str(timedelta(seconds=z))
            czasdur = str(timedelta(seconds=dur))
            e = discord.Embed(title=f"{member}", description=_(ctx.lang, "{mention} słucha **{title}** od **{artist}** na **{album}**\n\n**{czas}/{czasdur}**").format(mention=member.mention, title=member.activity.title, artist=member.activity.artist, album=member.activity.album, czas=czas, czasdur=czasdur), color=member.activity.color, timestamp=ctx.message.created_at)
            e.set_thumbnail(url=member.activity.album_cover_url)
            e.set_footer(icon_url=ctx.author.avatar_url)
            await ctx.send(embed=e)
        else:
            await ctx.send(_(ctx.lang, "**{member}** nie słucha nic na spotify.").format(member=member))

    @commands.command()
    async def history(self, ctx, limit=50):
        """Zwraca plik z historią wiadomości."""
        buf = io.BytesIO()
        tw = io.TextIOWrapper(buf, encoding='utf-8')
        n = 0
        lang = ctx.lang
        cor = "na"
        if lang == "ENG":
            cor = "on"
        async with ctx.channel.typing():
            async for message in ctx.channel.history(limit=limit):
                content = message.content
                if len(content) == 0:
                    continue
                if message.attachments:
                    content = message.attachments[0].url
                n += 1
                tw.write(f"#{n} {cor} {message.channel.name} * {message.author}  -  {content}  / {str(message.created_at)}\n")

        tw.flush()
        buf.seek(0)
        file = discord.File(filename=f"{ctx.channel.name}.txt", fp=buf)
        await ctx.send(file=file)

def setup(bot):
    bot.add_cog(Fun(bot))
