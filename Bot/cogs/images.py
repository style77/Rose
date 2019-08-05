import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
from math import cos, sin, radians, ceil
import textwrap
from io import BytesIO
from functools import partial
import random
from typing import Union
import typing
import numpy as np
import aiohttp
import io

from .classes.converters import urlConverter
from .utils import utils

status = {'online': (67, 181, 129),
          'idle': (250, 166, 26),
          'dnd': (240, 71, 71),
          'offline': (116, 127, 141)}
discord_neutral = (188, 188, 188)

class Images(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession(loop=bot.loop)
        dank_memer_token = utils.get_from_config("dank_token")
        self.dank_headers = {
            'Authorization': dank_memer_token
        }

    def random_color(self):
        color = list(np.random.choice(range(256), size=3))
        return tuple(color)

    async def get_avatar(self, ctx, user: Union[discord.User, discord.Member]) -> bytes:
        avatar_url = user.avatar_url_as(format="png")

        self.user = user
        self.ctx = ctx
        async with self.session.get(str(avatar_url)) as response:
            avatar_bytes = await response.read()

        return avatar_bytes

    # def processing_dsc(self, avatar_bytes: bytes, color: tuple, text, member) -> BytesIO:
    #     with Image.open(BytesIO(avatar_bytes)) as im:
    #         size = (35, 35)
    #         pic = r"images/krotki_dsc.png"
    #         with Image.new("RGB", (324, 60), (54, 57, 63)) as bg:
    #             rgb_avatar = im.convert("RGB")
    #             rgb_avatar.thumbnail(size)
    #             mask = Image.new('L', size, 0)
    #             draw = ImageDraw.Draw(mask)
    #             draw.ellipse(size, fill=255)
    #             rgb_avatar = ImageOps.fit(rgb_avatar, size, centering=(0.5, 0.5))
    #             rgb_avatar.putalpha(mask)
    #             bg.paste(rgb_avatar, (10, 11), mask)
    #             d = ImageDraw.Draw(bg)
    #             font = ImageFont.truetype(r"images/fonts/Whitney-Semibold.otf", 15)
    #             font2 = ImageFont.truetype(r"images/fonts/Whitney-Book.otf", 12)
    #             font3 = ImageFont.truetype(r"images/fonts/Whitney-Book.otf", 10, encoding='utf-8')
    #             role_color = member.top_role.color.to_rgb()
    #             if len(member.roles) == 1:
    #                 role_color = (255, 255, 255)
    #             if member.bot:
    #                 role_color = (255, 255, 255)
    #             if member.top_role.color.to_rgb() == (0, 0, 0):
    #                 role_color = (255, 255, 255)

    #             name = member.nick
    #             if name is None:
    #                 name = member.name

    #             d.text((56, 9), name, fill=role_color, font=font)
    #             width = d.textsize(name, font=font)
    #             text = u"{}".format(text)
    #             d.text((56, 32), text, fill=(255, 255, 255), font=font2)
    #             now = datetime.datetime.now()
    #             z= f"{now.strftime('%H')}:{now.strftime('%M')}"
    #             d.text((width[0]+66, 15), f"Today at {z}", fill=(94, 97, 101), font=font3)
    #             final_buffer = BytesIO()
    #             bg.save(final_buffer, "png")

    #     final_buffer.seek(0)
    #     return final_buffer

    def processing(self, text) -> BytesIO:
        fontpath = "images/fonts/Minecraft.ttf"
        with Image.new("RGB", (450,250), (31, 32, 33)) as bg:
            d = ImageDraw.Draw(bg)
            color = (255, 255, 255)
            text = textwrap.wrap(text, 24)
            text = "\n".join(text)
            if text.startswith('{~r}'):
                text = text.replace("{~r}", "")
                color = self.random_color()
            if text.startswith('{g}'):
                text = text.replace("{g}", "")
                color = random.choice([(173, 255, 47), (124, 252, 0), (0, 255, 0), (144, 238, 144)])
            if text.startswith('{b}'):
                text = text.replace("{b}", "")
                color = random.choice([(135,206,235), (135,206,250), (173,216,230), (176,224,230)])
            if text.startswith('{r}'):
                text = text.replace("{r}", "")
                color = random.choice([(220,20,60), (255,0,0), (255,69,0), (205,92,92)])
            font = ImageFont.truetype(fontpath, 30)
            d.text((10, 10), text, fill=color, font=font)
            final_buffer = BytesIO()
            bg.save(final_buffer, "png")

        final_buffer.seek(0)
        return final_buffer

    def processing_ac(self, text) -> BytesIO:
        fontpath = "images/fonts/Minecraft.ttf"
        with Image.open(r"images/a.png") as bg:
            d = ImageDraw.Draw(bg)
            color = (255, 255, 255)
            font = ImageFont.truetype(fontpath, 18)
            d.text((59, 38), text, fill=color, font=font)
            final_buffer = BytesIO()
            bg.save(final_buffer, "png")

        final_buffer.seek(0)
        return final_buffer

    @commands.command(aliases=['tb'])
    async def textbox(self, ctx, *, text: commands.clean_content="iam gay"):
        async with ctx.typing():
            texttocheck = textwrap.wrap(text, 24)
            if len(texttocheck) > 7:
                return await ctx.send(_(ctx.lang, "Ten tekst jest za długi."))
            fn = partial(self.processing, str(text))
            final_buffer = await self.bot.loop.run_in_executor(None, fn)
            file = discord.File(filename=f"{ctx.author.name}.png", fp=final_buffer)
            e = discord.Embed()
            e.set_image(url=f"attachment://{ctx.author.name}.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    #@commands.command()
    #async def fakie(self, ctx, member: typing.Optional[discord.Member]=None, *, text: commands.clean_content="Jestem gejem"):
        #"""używajcie tego z mózgiem prosze. Nie chcecie mieć problemów."""
        #member = member or ctx.author
        #if len(text) > 40:
            #return await ctx.send('Ten tekst jest za długi.')
        #async with ctx.typing():
            #if isinstance(member, discord.Member):
                #member_colour = member.colour.to_rgb()
            #else:
                #member_colour = (0, 0, 0)
            #avatar_bytes = await self.get_avatar(ctx, member)
            #fn = partial(self.processing_dsc, avatar_bytes, member_colour, text, member)
            #final_buffer = await self.bot.loop.run_in_executor(None, fn)
            #file = discord.File(filename=f"jebanko.png", fp=final_buffer)
            #await ctx.send(file=file)

    @commands.command(aliases=['a'])
    async def achievement(self, ctx, *, text: commands.clean_content="Jestem gejem"):
        async with ctx.typing():
            if len(text) > 20:
                return await ctx.send(_(ctx.lang, "Ten tekst jest za długi."))
            fn = partial(self.processing_ac, str(text))
            final_buffer = await self.bot.loop.run_in_executor(None, fn)
            file = discord.File(filename=f"siema.png", fp=final_buffer)
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    # Dankmember.services

    @commands.command()
    async def bed(self, ctx, url: urlConverter=None, url2: urlConverter=None):
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
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def hitler(self, ctx, url: urlConverter=None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/hitler", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def communism(self, ctx, url: urlConverter=None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/communism", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def gay(self, ctx, url: urlConverter=None):
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
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def jail(self, ctx, url: urlConverter=None):
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
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def dab(self, ctx, url: urlConverter=None):
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
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def brazzers(self, ctx, url: urlConverter=None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/brazzers", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def bongocat(self, ctx, url: urlConverter=None):
        async with ctx.typing():
            url = url or str(ctx.author.avatar_url)
            params = {
                'avatar1': url
            }
            async with aiohttp.ClientSession() as cs:
                async with cs.get("https://dankmemer.services/api/bongocat", headers=self.dank_headers, params=params) as r:
                    file = discord.File(fp=io.BytesIO(await r.read()), filename="siema.png")
            e = discord.Embed()
            e.set_image(url="attachment://siema.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    """
    https://github.com/CuteFwan/Koishi/blob/master/cufEDogs/stats.py#L126 <3
    """

    @commands.command(aliases=['pie'])
    async def piestatus(self, ctx, *, target: discord.Member = None):
        target = target or ctx.author
        async with ctx.channel.typing():
            row = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", target.id)
            if not row:
                return await ctx.send(_(ctx.lang, "{}, nie posiada konta premium.").format(target.mention))
            async with self.bot.session.get(str(target.avatar_url_as(format='png'))) as r:
                avydata = io.BytesIO(await r.read())
            data = dict()
            data['online'] = row[0]['online']
            data['offline'] = row[0]['offline']
            data['idle'] = row[0]['idle']
            data['dnd'] = row[0]['dnd']
            data = await self.bot.loop.run_in_executor(None, self._piestatus, avydata, data)
            await ctx.send(file=discord.File(data, filename=f'{target.display_name}_pie_status.png'))

    def _piestatus(self, avydata, statuses):
        total = sum(statuses.values())
        stat_deg = {k: (v/total)*360 for k, v in statuses.items()}
        angles = dict()
        starting = -90
        for k, v in stat_deg.items():
            angles[k] = starting + v
            starting += v
        base = Image.new(mode='RGBA', size=(400, 300), color=(0, 0, 0, 0))
        piebase = Image.new(mode='RGBA', size=(400, 300), color=(0, 0, 0, 0))
        with Image.open(avydata).resize((200, 200), resample=Image.BICUBIC).convert('RGBA') as avy:
            with Image.open(r'images/piestatustest2.png').convert('L') as mask:
                base.paste(avy, (50, 50), avy)
                draw = ImageDraw.Draw(piebase)
                maskdraw = ImageDraw.Draw(mask)
                starting = -90
                for k, v in angles.items():
                    if starting == v:
                        continue
                    else:
                        draw.pieslice(((-5, -5), (305, 305)),
                                      starting, v, fill=status[k])
                        starting = v
                if not 360 in stat_deg:
                    mult = 1000
                    offset = 150
                    for k, v in angles.items():
                        x = offset + ceil(offset * mult *
                                          cos(radians(v))) / mult
                        y = offset + ceil(offset * mult *
                                          sin(radians(v))) / mult
                        draw.line(((offset, offset), (x, y)),
                                  fill=(255, 255, 255, 255), width=1)
                del maskdraw
                piebase.putalpha(mask)
        font = ImageFont.truetype(r"images/fonts/light.otf", 15)
        bx = 310
        by = {'online': 60, 'idle': 110, 'dnd': 160, 'offline': 210}
        base.paste(piebase, None, piebase)
        draw = ImageDraw.Draw(base)
        for k, v in statuses.items():
            draw.rectangle(((bx, by[k]), (bx+30, by[k]+30)),
                           fill=status[k], outline=(255, 255, 255, 255))
            draw.text(
                (bx+40, by[k]+8), f'{(v/total)*100:.2f}%', fill=discord_neutral, font=font)
        del draw
        buffer = io.BytesIO()
        base.save(buffer, 'png')
        buffer.seek(0)
        return buffer

    def processing2(self, avatar_bytes: bytes, colour: tuple, path, position, size) -> BytesIO:
        with Image.open(BytesIO(avatar_bytes)) as im:
            im.thumbnail((200,200))
            with Image.new("RGB", im.size, colour) as background:
                rgb_avatar = im.convert("RGB")
                rgb_avatar.thumbnail((250,250))
                background.paste(rgb_avatar, (0,0))
                hat = Image.open(path)
                hat.thumbnail(size)
                background.paste(hat, position, mask=hat)
                final_buffer = BytesIO()
                background.save(final_buffer, "png")
        final_buffer.seek(0)

        return final_buffer

    @commands.command()
    async def hat(self, ctx, member: urlConverter=None, *, hat_name=None):
        """Zwraca obrazek z czapką na twoim lub czyimś awatarze."""
        member = member or ctx.author
        hats_dict = {
                    "christmas": [r"images/christmas_hat.png", (60, 10), (130, 130)],
                    "witch": [r"images/witch_hat.png", (60, 10), (155, 155)],
                    "autism": [r"images/autism_hat.png", (45, 10), (110, 110)],
                    "wiatraczek_kurwa": [r"images/wiatraczek_kurwa_hat.png", (45, 10), (110, 110)],
                    "incognito": [r"images/incognito_hat.png", (40, 20), (125, 125)],
                    "?x?x?xxx??": [r"images/you_wont_find_this_hat.png", (40, 3), (120, 120)]
                    }

        if not hat_name in hats_dict:
            return await ctx.send(_(ctx.lang, "Nie ma takiej czapki. Spróbuj {hats}").format(hats=', '.join([hat for hat in hats_dict])))

        async with ctx.typing():
            if isinstance(member, discord.Member):
                member_colour = member.colour.to_rgb()
            else:
                member_colour = (0, 0, 0)

            h = hats_dict[hat_name]

            avatar_bytes = await self.get_avatar(ctx, member)
            fn = partial(self.processing2, avatar_bytes,
                         member_colour, h[0], h[1], h[2])
            final_buffer = await self.bot.loop.run_in_executor(None, fn)
            file = discord.File(filename=f"{member.id}.png", fp=final_buffer)
            e = discord.Embed()
            e.set_image(url=f"attachment://{member.id}.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def tweet(self, ctx, member: typing.Optional[discord.Member]=None, *, text: str="iam gay"):
        """Tworzy tweeta."""
        member = member or ctx.author
        async with ctx.typing():
            f = await self.bot.app.tweet(str(member.avatar_url), text, member.name)
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def blurple(self, ctx, url: urlConverter=None):
        """Tworzy obrazek oparty na 3 kolorach discorda."""
        url = url or str(ctx.author.avatar_url)
        async with ctx.typing():
            f = await self.bot.app.blurple(url)
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def triggered(self, ctx, url: urlConverter=None):
        url = url or str(ctx.author.avatar_url)
        async with ctx.typing():
            f = await self.bot.app.triggered(url)
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.gif")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.group(invoke_without_command=True)
    async def anime(self, ctx):
        """be careful."""
        z = []
        for cmd in self.bot.get_command("anime").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz użyć:\n```\n{}```").format('\n'.join(z)))

    @anime.command()
    async def cuddle(self, ctx):
        async with ctx.typing():
            f = await self.bot.app.cuddle
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.gif")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @anime.command()
    async def hug(self, ctx):
        async with ctx.typing():
            f = await self.bot.app.hug
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.gif")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @anime.command()
    async def pat(self, ctx):
        async with ctx.typing():
            f = await self.bot.app.pat
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.gif")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @anime.command()
    async def kiss(self, ctx):
        async with ctx.typing():
            f = await self.bot.app.cuddle
            e = discord.Embed()
            e.set_image(url=f"attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            await ctx.send(file=await f.get_discord_file(), embed=e)

def setup(bot):
    bot.add_cog(Images(bot))
