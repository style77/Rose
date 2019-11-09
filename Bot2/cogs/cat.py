import asyncio
import functools
import random
from enum import Enum
from io import BytesIO

import aiohttp
import typing

import discord
from PIL import ImageFont, ImageDraw, ImageOps, Image
from discord.ext import commands, tasks


class SlotsEmojis(Enum):
    CACTUS = "\U0001f335"
    GEM = "\U0001f48e"
    HEART = "\U00002764"
    SPARKLING_HEART = "\U0001f496"
    STAR = "\U00002b50"
    ROSE = "\U0001f339"


class CatIsDead(commands.CommandError):
    pass


class MemberDoesNotHaveCat(commands.CommandError):
    pass


class DefaultCat:
    """Default representation for cats"""
    def __init__(self, bot, cat):
        self.bot = bot
        self.cat = cat

    def __getattr__(self, attr):
        if attr == "owner":
            return self._owner
        if attr == "stamina":
            attr = "sta"
        if attr == "health":
            attr = "hp"
        return self.cat[attr]

    @property
    def _owner(self):
        user = self.bot.get_user(self.cat['owner_id'])
        return user


class Cat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.losing_food.start()
        self.losing_sta.start()
        self.sleeping_restore.start()
        self.session = aiohttp.ClientSession(loop=bot.loop)
        self.rose_team = [185712375628824577, 403600724342079490]
        self.cost = {
            "karma": 2000,
            "energy drink": 22000,
            "health drink": 24000,
            "food drink": 20000,
        }

    def cog_unload(self):
        self.losing_food.cancel()
        self.losing_sta.cancel()
        self.sleeping_restore.cancel()

    async def get_cat(self, member):
        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", member.id)
        if await self.is_dead(member):
            raise CatIsDead()
        if not cat:
            raise MemberDoesNotHaveCat()
        return DefaultCat(self.bot, cat)

    async def lvl_up(self, cat: DefaultCat):
        if cat.exp > round(700 * cat.level):
            await self.bot.db.execute("UPDATE cats SET level = level + 1, money = money + 65  WHERE owner_id = $1",
                                          cat.owner_id)
            return True
        else:
            return False

    async def is_dead(self, member):
        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", member.id)
        if not cat:
            return

        cat = DefaultCat(self.bot, cat)

        if cat.food <= 0:
            await self.bot.db.execute("UPDATE cats SET is_dead = True, is_sleeping = False WHERE owner_id = $1",
                                          member.id)
            return True

        if cat.stamina <= 0:
            await self.bot.db.execute("UPDATE cats SET is_dead = True WHERE owner_id = $1", member.id)
            return True

        if cat.health <= 0:
            await self.bot.db.execute("UPDATE cats SET is_dead = True, is_sleeping = False WHERE owner_id = $1",
                                          member.id)
            return True

        if cat.is_dead:
            return True

        return False

    @tasks.loop(minutes=120)
    async def losing_food(self):
        await self.bot.db.execute("UPDATE cats SET food = food - 1 WHERE food > 0")
        await self.bot.db.execute("UPDATE cats SET is_dead = TRUE WHERE food = 0")

    @tasks.loop(seconds=60)
    async def sleeping_restore(self):
        await self.bot.db.execute("UPDATE cats SET sta = sta + 1, sleeping_time = sleeping_time + 1 WHERE sta < 100 AND is_sleeping = TRUE AND is_dead = FALSE")

    @tasks.loop(minutes=75)
    async def losing_sta(self):
        await self.bot.db.execute("UPDATE cats SET sta = sta - 1 WHERE sta > 0 AND is_sleeping = FALSE")
        await self.bot.db.execute("UPDATE cats SET is_dead = TRUE WHERE sta = 0")

    @losing_food.before_loop
    @sleeping_restore.before_loop
    @losing_sta.before_loop
    async def b4_tasks(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def progress_bar(draw, y: int, color: tuple, progress: int):
        draw.rectangle(((41, y), (42 + (round(progress * 3.34)), y + 27)), fill=color)

    @staticmethod
    def write(image, text, cords: tuple, font, color: tuple = (0, 0, 0)):
        image.text(cords, text, fill=color, font=font)

    async def get_avatar(self, user: typing.Union[discord.User, discord.Member]) -> bytes:
        avatar_url = user.avatar_url_as(format="png")

        async with self.session.get(str(avatar_url)) as response:
            avatar_bytes = await response.read()

        return avatar_bytes

    def processing(self, avatar_bytes: bytes, cat, image_path, ctx) -> BytesIO:  # color: tuple,
        with Image.open(BytesIO(avatar_bytes)) as im:
            pic = r"assets/images/profile.png"
            size = 80, 80
            theme = cat.theme

            with Image.open(image_path) as caty:
                caty = caty.convert("RGBA")
                caty = caty.resize((240, 240))

                with Image.open(pic) as profile:
                    bg = Image.new('RGBA', (700, 800))
                    if theme:
                        end = ".png"
                        if theme == 'jungle1':
                            end = '.jpg'
                        theme = Image.open(r"assets/images/themes/" + theme + end)
                        bg.paste(theme)

                    bg.paste(profile, (0, 0), profile)

                    mask = Image.new('L', size, 0)
                    draw = ImageDraw.Draw(mask)
                    draw.ellipse((0, 0) + size, fill=255)

                    rgb_avatar = ImageOps.fit(im, size, centering=(0.5, 0.5))
                    rgb_avatar.putalpha(mask)
                    rgb_avatar.thumbnail(size)

                    bg.paste(caty, (44, 105), caty)
                    bg.paste(rgb_avatar, (35, 10), rgb_avatar)

                    d = ImageDraw.Draw(bg)

                    font = ImageFont.truetype(
                        r"assets/images/fonts/light.otf", 45)
                    emoji_font = ImageFont.truetype(
                        r"assets/images/fonts/emotes.otf", 45)

                    name = cat.name
                    if len(name) > 12:
                        name = name[:12] + "..."

                    self.write(
                        d,
                        name,
                        (330, 100),
                        font=font,
                        color=(255, 255, 255))

                    if cat.owner.id in self.rose_team:
                        width = d.textsize(name, font=font)
                        self.write(d, "\U0001f339", (width[0] + 335, 110),
                                   font=emoji_font, color=(255, 255, 255))

                    self.write(
                        d,
                        str(cat.premium),
                        (500, 211),
                        font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    self.write(
                        d,
                        '{:,d}'.format(int(cat.money)),
                        (470, 254),
                        font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    self.write(
                        d,
                        str(cat.level),
                        (460, 304),
                        font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    if ctx.guild:
                        guild_name = ctx.guild.name
                        if len(guild_name) > 18:
                            guild_name = guild_name[:18] + "..."
                        self.write(d, guild_name, (10, 765), font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 15))

                    self.progress_bar(d, 441, (52, 152, 219), cat.stamina)
                    self.write(d, str(cat.stamina), (175, 435), font=ImageFont.truetype(
                        r"assets/images/fonts/medium.otf", 30))
                    self.progress_bar(d, 548, (46, 204, 113), cat.food)
                    self.write(d, str(cat.food), (175, 542), font=ImageFont.truetype(
                        r"assets/images/fonts/medium.otf", 30))
                    self.progress_bar(d, 647, (233, 30, 64), cat.health)
                    self.write(d, str(cat.health), (175, 641), font=ImageFont.truetype(
                        r"assets/images/fonts/medium.otf", 30))
                    final_buffer = BytesIO()
                    bg.save(final_buffer, "png")

        final_buffer.seek(0)
        return final_buffer

    @commands.command()
    async def adopt(self, ctx):
        """Adoptuj swojego zwierzaka"""
        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", ctx.author.id)
        if cat:
            return await ctx.send(ctx.lang['already_has_cat'])

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        kolor = random.choice(["czarnego",
                               "szarego",
                               "brązowego"])

        colors = {"czarnego": "black",
                  "szarego": "grey",
                  "brązowego": "brown"}

        await ctx.send(ctx.lang['adopted_cat']).format(ctx.lang[kolor])

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(ctx.lang['TimeoutError'])

        name = msg.content
        name = name[:1].upper() + name[1:].lower()
        k = colors[kolor]
        await self.bot.db.execute("INSERT INTO cats (owner_id, name, color) VALUES ($1, $2, $3)",
                                      ctx.author.id, name, k)
        return await ctx.send(ctx.lang['cat_will_be_called'].format(name=name))

    @commands.group(invoke_without_command=True, aliases=['profile'])
    async def cat(self, ctx, member: discord.Member = None):
        """Pokazuje profil twojego kota."""
        member = member or ctx.author
        cat = await self.get_cat(member)
        if cat.is_sleeping:
            return await ctx.send(ctx.lang['cat_is_sleeping'])
        if cat.is_sleeping and cat.stamina == 100:
            return await ctx.send(ctx.lang['full_sta_sleeping_cat'])
        kolor = cat.color
        path = r"assets/images/cats/{}/{}.png"
        image_path = path.format(kolor, 1)

        async with ctx.typing():
            avatar_bytes = await self.get_avatar(member)
            fn = functools.partial(self.processing, avatar_bytes,
                                   cat, image_path, ctx)
            final_buffer = await self.bot.loop.run_in_executor(None, fn)
            file = discord.File(filename=f"{cat.name}.png", fp=final_buffer)
            await ctx.send(file=file)


def setup(bot):
    bot.add_cog(Cat(bot))
