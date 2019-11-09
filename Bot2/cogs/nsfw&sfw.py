import base64
import colorsys
import io
import random

import aiohttp
import discord
from discord import Color
from discord.ext import commands

from .utils import get
from .classes.other import Plugin


FLOWER_HEADERS = {
    "Authorization": get('flower_api_key')
}


class SFW(Plugin):
    """I dont promise that all images are safe."""
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.channel.is_nsfw()

    @commands.command(aliases=['asians'])
    async def asian(self, ctx):
        async with ctx.typing():
            async with aiohttp.ClientSession(loop=self.bot.loop) as cs:
                async with cs.get("http://149.202.62.19/api/asians", headers=FLOWER_HEADERS) as r:
                    file = await r.read()
                    file_data = r.headers
                    file_name = "\U0001f609"

                    file_format = file_data['Content-Type'].replace("image/", "")

                    fn = f"gay.{file_format}"
                    file = discord.File(fp=io.BytesIO(file), filename=fn)

            values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
            e = discord.Embed(title=file_name, color=Color.from_rgb(*values))
            e.set_image(url=f"attachment://{fn}")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)


class NSFW(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    def cog_check(self, ctx):
        return ctx.channel.is_nsfw()

    @commands.command(aliases=["toocuteforporn"])
    async def toocute(self, ctx):
        async with ctx.typing():
            async with aiohttp.ClientSession(loop=self.bot.loop) as cs:
                async with cs.get("http://149.202.62.19/api/nsfw/toocute", headers=FLOWER_HEADERS) as r:
                    file = await r.read()
                    file_data = r.headers
                    file_name = "\U0001f609"

                    file_format = file_data['Content-Type'].replace("image/", "")

                    fn = f"gay.{file_format}"
                    file = discord.File(fp=io.BytesIO(file), filename=fn)

            values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
            e = discord.Embed(title=file_name, color=Color.from_rgb(*values))
            e.set_image(url=f"attachment://{fn}")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command(aliases=["publicnsfw"])
    async def public(self, ctx):
        async with ctx.typing():
            async with aiohttp.ClientSession(loop=self.bot.loop) as cs:
                async with cs.get("http://149.202.62.19/api/nsfw/public", headers=FLOWER_HEADERS) as r:
                    file = await r.read()
                    file_data = r.headers
                    file_name = "\U0001f609"

                    file_format = file_data['Content-Type'].replace("image/", "")

                    fn = f"gay.{file_format}"
                    file = discord.File(fp=io.BytesIO(file), filename=fn)

            values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
            e = discord.Embed(title=file_name, color=Color.from_rgb(*values))
            e.set_image(url=f"attachment://{fn}")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def ass(self, ctx):
        async with ctx.typing():
            async with aiohttp.ClientSession(loop=self.bot.loop) as cs:
                async with cs.get("http://149.202.62.19/api/nsfw/ass", headers=FLOWER_HEADERS) as r:
                    file = await r.read()
                    file_data = r.headers
                    file_name = "\U0001f609"

                    file_format = file_data['Content-Type'].replace("image/", "")

                    fn = f"gay.{file_format}"
                    file = discord.File(fp=io.BytesIO(file), filename=fn)

            values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
            e = discord.Embed(title=file_name, color=Color.from_rgb(*values))
            e.set_image(url=f"attachment://{fn}")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)

    @commands.command()
    async def boobs(self, ctx):
        async with ctx.typing():
            async with aiohttp.ClientSession(loop=self.bot.loop) as cs:
                async with cs.get("http://149.202.62.19/api/nsfw/boobs", headers=FLOWER_HEADERS) as r:
                    file = await r.read()
                    file_data = r.headers
                    file_name = "\U0001f609"

                    file_format = file_data['Content-Type'].replace("image/", "")

                    fn = f"gay.{file_format}"
                    file = discord.File(fp=io.BytesIO(file), filename=fn)

            values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
            e = discord.Embed(title=file_name, color=Color.from_rgb(*values))
            e.set_image(url=f"attachment://{fn}")
            e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")
            await ctx.send(file=file, embed=e)


def setup(bot):
    bot.add_cog(SFW(bot))
    bot.add_cog(NSFW(bot))
