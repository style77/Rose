# not for kids
# yes im kid
# but im not using this
# i wasnt even testing this

import discord
import nekos
from discord.ext import commands

from Bot.cogs.classes.plugin import Plugin

class Nsfw(Plugin):
    def __init__(self, bot):
        self.bot = bot

    def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        elif ctx.channel.is_nsfw():
            return True
        else:
            raise commands.NSFWChannelRequired(ctx.channel)

    @commands.command()
    async def cum(self, ctx):
        try:
            async with ctx.typing():
                e = discord.Embed()
                e.set_image(url=nekos.img("cum"))
                e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
                await ctx.send(embed=e)
        except Exception as e:
            return await ctx.send(e)

    @commands.command()
    async def yuri(self, ctx):
        try:
            async with ctx.typing():
                e = discord.Embed()
                e.set_image(url=nekos.img("yuri"))
                e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
                await ctx.send(embed=e)
        except Exception as e:
            return await ctx.send(e)

    @commands.command()
    async def lewd(self, ctx):
        try:
            async with ctx.typing():
                e = discord.Embed()
                e.set_image(url=nekos.img("lewd"))
                e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
                await ctx.send(embed=e)
        except Exception as e:
            return await ctx.send(e)

    @commands.command(aliases=["snap"])
    async def snapchat(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.snapchat
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def teen(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.teen
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command(aliases=["cycki"])
    async def boobs(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.boobs
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def nsfwgif(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.gif")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.porngif
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def ass(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.ass
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def milf(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.milf
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def lesbian(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.lesbian
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def hentai(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(
                text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.hentai
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def gonewild(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.gonewild
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command(aliases=['bj'])
    async def blowjob(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.blowjob
            await ctx.send(file=await f.get_discord_file(), embed=e)

    @commands.command()
    async def pussy(self, ctx):
        async with ctx.typing():
            e = discord.Embed()
            e.set_image(url="attachment://nothing.png")
            e.set_footer(text="🌹 " + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))
            f = await self.bot.app.pussy
            await ctx.send(file=await f.get_discord_file(), embed=e)

def setup(bot):
    bot.add_cog(Nsfw(bot))
