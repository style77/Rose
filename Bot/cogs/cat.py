import asyncio
import collections
import functools
import math
import random
import time
from enum import Enum
from io import BytesIO

import aiohttp
import typing

import discord
from PIL import ImageFont, ImageDraw, ImageOps, Image
from discord.ext import commands, tasks

from Bot2.cogs.classes import other
from .classes.converters import AmountConverter
from .utils import fuzzy, get_language


class SlotsEmojis(Enum):
    CACTUS = "\U0001f335"
    GEM = "\U0001f48e"
    HEART = "\U00002764"
    SPARKLING_HEART = "\U0001f496"
    STAR = "\U00002b50"
    ROSE = "\U0001f339"


class CatError(commands.CommandError):
    def __init__(self, type_):
        self.type = type_


class CatIsDead(CatError):
    def __init__(self):
        super().__init__('dead')


class MemberDoesNotHaveCat(CatError):
    def __init__(self):
        super().__init__('no_cat')


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

    async def buy(self, item):
        try:
            cost = COST[item]
        except KeyError:
            cost = WEAPONS_PRICE[item]

        self.cat['inventory'].append(item)

        await self.bot.db.execute("UPDATE cats SET money = money - $1, inventory = $2 WHERE owner_id = $3", cost,
                                  self.inventory, self.cat['owner_id'])

        return self.money - cost

    async def sell(self, item):
        try:
            price = COST[item]
        except KeyError:
            price = WEAPONS_PRICE[item]

        self.cat['inventory'].remove(item)

        await self.bot.db.execute("UPDATE cats SET money = money + ($1 / 2), inventory = $2 WHERE owner_id = $3", price,
                                  self.inventory, self.cat['owner_id'])

        return self.money + round(price / 2)


WEAPON_DAMAGE_MAP = {
    "glock-6": 17,
    "shovel": 9,
    "glock-9": 12,
    "usp-s": 17,
    "axe": 13,
    "p90": 16,  # 999
    "mp7": 17,
    "mac-10": 27300,
    "mp9": 17,
    "m4a1": 23,
    "deagle": 66,
    "glock-17": 19,
    "ak-47": 24,
    "beretta": 25,
    "thompson": 28,
    "m16": 34,
    "awp": 79,
    "luger": 72
}

WEAPON_RELOAD_MAP = {
    "glock-6": 1,
    "shovel": 2,
    "glock-9": 1,
    "usp-s": 1,
    "axe": 2,
    "p90": 1,
    "mp7": 1,
    "mac-10": 1,
    "mp9": 1,
    "m4a1": 1,
    "deagle": 4,
    "glock-17": 1,
    "ak-47": 1,
    "beretta": 2,
    "thompson": 1,
    "m16": 2,
    "awp": 3,
    "luger": 3
}


class Weapon:
    def __init__(self, type_):
        self.type = type_

        self.reloaded = True

        self._reload_in = 0  # rounds
        if type_ not in WEAPON_RELOAD_MAP:
            raise ValueError(f"{type_} not in reload_map")
        self.__default_reload = WEAPON_RELOAD_MAP[type_]

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'<Weapon type={self.type}>'

    @property
    def raw(self):
        return self.type

    @property
    def damage(self):
        try:
            return WEAPON_DAMAGE_MAP[self.type]
        except KeyError:
            return None

    @property
    def reload_in(self):
        return self._reload_in

    def _shoot(self, enemy):
        enemy.hp -= random.randint(self.damage - 5, self.damage + 4)

    def shoot(self, enemy: collections.namedtuple):
        if self.reloaded:
            self.reloaded = False
            self._reload_in = self.__default_reload

            self._shoot(enemy)

            self._reload_in -= 1

        elif self.__default_reload == 1:
            self._shoot(enemy)
        elif self._reload_in == 0:
            self.reloaded = True
        else:
            self._reload_in -= 1


ALL_WEAPONS = ['ak-47', 'knife', 'm4a1', 'm16', 'glock-17', 'glock-9', 'glock-6', 'desert eagle', 'awp', 'usp-s',
               'thompson', 'beretta', 'luger', 'p90', 'mp7', 'mac-10', 'mp9', 'axe', 'shovel']


class Box:
    def __init__(self, type_):
        self.type = type_

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return f'<Box type={self.type}>'

    @property
    def raw(self):
        return self.type


ALL_BOXES = ['common_box', 'rare_box', 'epic_box', 'legendary_box', 'pretty_box']


class ItemsConverter(commands.Converter):
    def __init__(self, type_):
        self.type = type_

    async def convert(self, ctx, argument):
        if self.type == 'box':
            box = fuzzy.extract_one(argument, ALL_BOXES, score_cutoff=60)

            if not box:
                return None

            box = box[0]

            return Box(box)

        elif self.type == 'weapon':
            weapon = fuzzy.extract_one(argument, ALL_WEAPONS, score_cutoff=60)

            if not weapon:
                return None

            weapon = weapon[0]

            return Weapon(weapon)

        elif self.type == 'item':
            item = fuzzy.extract_one(argument, ALL_ITEMS, score_cutoff=60)

            if not item:
                return None

            item = item[0]

            return item

        else:
            raise NotImplemented(f"{self.type} is not implemented in this converter.")


COST = {
    "karma": 2000,
    "energy drink": 22000,
    "health drink": 24000,
    "food drink": 20000,

    "common_box": 7000,
    "rare_box": 14500,
    "epic_box": 46000,
    "legendary_box": 320000,
}

WEAPONS_PRICE = {
    "glock-6": 12500,
    "shovel": 9500,
    "glock-9": 14000,
    "usp-s": 17000,
    "axe": 10000,
    "p90": 12000,
    "mp7": 16000,
    "mac-10": 27300,
    "mp9": 32000,
    "m4a1": 29200,
    "deagle": 26700,
    "glock-17": 22420,
    "ak-47": 92000,
    "beretta": 62000,
    "thompson": 175000,
    "m16": 340000,
    "awp": 420000,
    "luger": 1700000
}

ALL_ITEMS = ["karma", "energy drink", "food drink", "health drink"]
ALL_ITEMS.extend(ALL_BOXES)
ALL_ITEMS.extend(ALL_WEAPONS)

BOX_MAP = {
    "common_box": ['glock-6', 'shovel', 'glock-9', 'usp-s', 'p90'],
    "rare_box": ['axe', 'm4a1', 'desert eagle', 'glock-17', 'mp7'],
    "epic_box": ['ak-47', 'beretta', 'thompson', 'm16', 'mac-10', 'mp9'],
    "legendary_box": ['awp', 'luger'],
    "pretty_box": ['legendary_box']  # todo ...
}

BOX_COLOR_MAP = {
    "common_box": discord.Color.greyple(),
    "rare_box": discord.Color.blue(),
    "epic_box": discord.Color.red(),
    "legendary_box": discord.Color.gold(),
    "pretty_box": discord.Color.dark_purple()
}


class Cat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        self.losing_food.start()
        self.losing_sta.start()
        self.sleeping_restore.start()

        self.rose_team = [185712375628824577, 403600724342079490]

        self._fights = list()

    def cog_unload(self):
        self.losing_food.cancel()
        self.losing_sta.cancel()
        self.sleeping_restore.cancel()

    # async def update_cache(self, cat):
    #     user = self.bot.get_user(cat.owner_id)
    #
    #     cat_ = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", cat.owner_id)
    #     new_cat = DefaultCat(self.bot, cat_)
    #
    #     if cat.owner_id in self._cats_cache:
    #         self._cats_cache[cat.owner_id] = new_cat
    #
    #     if cat.owner_id in self._processing_cache:
    #         path = r"assets/images/cats/{}/{}.png"
    #         image_path = path.format(new_cat.color, 1)
    #
    #         avatar_bytes = await self.get_avatar(user)
    #
    #         fn = functools.partial(self.processing, avatar_bytes, new_cat, image_path, user)
    #         final_buffer = await self.bot.loop.run_in_executor(None, fn)
    #
    #         self._processing_cache[user.id] = final_buffer

    async def _prepare_trivia(self, ctx, *, diff=None):
        trivia_url = "https://opentdb.com/api.php?amount=1500&type=multiple"
        if diff is not None:
            trivia_url += f'&difficulty={diff}'

        async with self.bot.session.get(trivia_url) as req:
            data = await req.json()

        trivia = random.choice(data['results'])

        e = discord.Embed(
            description=f"{ctx.lang['category']}: {trivia['category']}\n{ctx.lang['difficulty']}: "
                        f"{trivia['difficulty']}\n{ctx.lang['you_have']} **60** {ctx.lang['seconds']}.",
            timestamp=ctx.message.created_at)

        question = trivia['question'].replace('&#039;', "'")
        question = question.replace('&quot;', "“")

        e.set_author(name=question)

        numbers = [
            '1\N{combining enclosing keycap}',
            '2\N{combining enclosing keycap}',
            '3\N{combining enclosing keycap}',
            '4\N{combining enclosing keycap}'
        ]

        answers = [trivia['correct_answer']]

        answers.extend(trivia['incorrect_answers'])

        random.shuffle(answers)

        data = {}

        for number, quest in zip(numbers, answers):

            quest = quest.replace('&#039;', "'")
            quest = quest.replace('&quot;', "“")

            data[number] = quest

            e.add_field(name=number, value=data[number], inline=False)

        message = await ctx.send(embed=e)
        for number in numbers:
            await message.add_reaction(number)

        def check(reaction, user):
            return user == ctx.author and reaction.message.channel.id == ctx.channel.id

        try:
            r, u = await self.bot.wait_for('reaction_add', check=check, timeout=60)
        except asyncio.TimeoutError:
            return await ctx.send(ctx.lang['TimeoutError'])

        correct = None

        for key, value in data.items():
            if value == trivia['correct_answer']:
                correct = key

        if r.emoji == correct:
            return True, trivia['correct_answer'], trivia['difficulty']
        return False, trivia['correct_answer'], trivia['difficulty']

    async def get_cat(self, member):
        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", member.id)
        guild = await self.bot.get_guild_settings(member.guild.id)
        lang = self.bot.polish if guild.lang == "PL" else self.bot.english
        if await self.is_dead(member):
            raise commands.BadArgument(f"{member}, {lang['dead_cat'].format(guild.prefix)}")
        if not cat:
            raise commands.BadArgument(f"{member}, {lang['no_cat'].format(guild.prefix)}")
        return DefaultCat(self.bot, cat)

    async def lvl_up(self, cat):
        if cat['exp'] > round(700 * cat['level']):
            await self.bot.db.execute("UPDATE cats SET level = level + 1, money = money + 65  WHERE owner_id = $1",
                                      cat['owner_id'])
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

    @tasks.loop(minutes=180)
    async def losing_food(self):  # todo notify about low food,sta
        await self.bot.db.execute("UPDATE cats SET food = food - 1 WHERE food > 0")
        await self.bot.db.execute("UPDATE cats SET is_dead = TRUE WHERE food = 0")

    @tasks.loop(seconds=60)
    async def sleeping_restore(self):
        await self.bot.db.execute("UPDATE cats SET sta = sta + 1, sleeping_time = sleeping_time + 1 WHERE sta < 100 AND is_sleeping = true AND is_dead = false")
        await self.bot.db.execute("UPDATE cats SET sleeping_time = 0 AND is_sleeping = false WHERE is_sleeping = true AND sta = 100")

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

        async with self.bot.session.get(str(avatar_url)) as response:
            avatar_bytes = await response.read()

        return avatar_bytes

    def processing(self, avatar_bytes: bytes, cat, image_path, user) -> BytesIO:  # color: tuple,
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

                    PISTOLS = ['glock_17', 'glock-6', 'glock-9']

                    if cat.wore_gun:
                        if cat.wore_gun in PISTOLS:
                            x, y = 80, 200
                            size = (10, 10)
                        else:
                            x, y = 70, 240
                            size = (188, 120)

                        gun = Image.open(f'assets/images/guns/{cat.wore_gun}.png')
                        gun = gun.convert("RGBA")
                        gun = gun.resize(size, Image.ANTIALIAS)

                        bg.paste(gun, (x, y), gun)

                    d = ImageDraw.Draw(bg)

                    font = ImageFont.truetype(r"assets/images/fonts/light.otf", 45)
                    emoji_font = ImageFont.truetype(r"assets/images/fonts/emotes.otf", 45)

                    name = cat.name
                    if len(name) > 12:
                        name = name[:12] + "..."

                    self.write(d, name, (330, 100), font=font, color=(255, 255, 255))

                    if cat.owner.id in self.rose_team:
                        width = d.textsize(name, font=font)
                        self.write(d, "\U0001f339", (width[0] + 335, 110), font=emoji_font, color=(255, 255, 255))

                    self.write(d, str(cat.premium), (500, 211),
                               font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    self.write(d, '{:,d}'.format(int(cat.money)), (470, 254),
                               font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    self.write(d, str(cat.level), (460, 304),
                               font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))

                    member_name = user.name
                    if len(member_name) > 18:
                        member_name = member_name[:18] + "..."
                    self.write(d, member_name, (10, 765), font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 15))

                    self.progress_bar(d, 441, (52, 152, 219), cat.stamina)
                    self.write(d, str(cat.stamina), (175, 435), font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))
                    self.progress_bar(d, 548, (46, 204, 113), cat.food)
                    self.write(d, str(cat.food), (175, 542), font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))
                    self.progress_bar(d, 647, (233, 30, 64), cat.health)
                    self.write(d, str(cat.health), (175, 641), font=ImageFont.truetype(r"assets/images/fonts/medium.otf", 30))
                    final_buffer = BytesIO()
                    bg.save(final_buffer, "png")

        final_buffer.seek(0)
        return final_buffer

    @commands.group(invoke_without_command=True, aliases=['profile'])
    async def cat(self, ctx, member: discord.Member = None):
        """Pokazuje profil twojego kota."""
        member = member or ctx.author
        cat = await self.get_cat(member)

        if cat.is_sleeping:
            return await ctx.send(ctx.lang['cat_is_sleeping'])

        if cat.is_sleeping and cat.stamina == 100:
            return await ctx.send(ctx.lang['full_sta_sleeping_cat'])

        async with ctx.typing():
            start = time.time()

            # if ctx.author.id in self._processing_cache:
            #     buffer = self._processing_cache[ctx.author.id]
            #     buffer.seek(0)
            #     file = discord.File(filename=f"{ctx.author.id}.png", fp=buffer)
            #
            #     end = time.time()
            #     await ctx.send(f"Done in: {round(end-start, 4)}s", file=file)
            # else:
            path = r"assets/images/cats/{}/{}.png"
            image_path = path.format(cat.color, 1)

            avatar_bytes = await self.get_avatar(member)

            fn = functools.partial(self.processing, avatar_bytes, cat, image_path, ctx.author)
            final_buffer = await self.bot.loop.run_in_executor(None, fn)

            # self._processing_cache[ctx.author.id] = final_buffer

            file = discord.File(filename=f"{ctx.author.id}.png", fp=final_buffer)

            end = time.time()
            await ctx.send(f"Done in: {round(end-start, 2)}s", file=file)

    @cat.command()
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

        await ctx.send(ctx.lang['adopted_cat'].format(ctx.lang[kolor]))

        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(ctx.lang['TimeoutError'])

        name = msg.content
        name = name[:1].upper() + name[1:].lower()
        k = colors[kolor]
        await self.bot.db.execute("INSERT INTO cats (owner_id, name, color) VALUES ($1, $2, $3)",
                                  ctx.author.id, name, k)
        return await ctx.send(ctx.lang['cat_will_be_called'].format(name))

    @commands.command()
    async def roulette(self, ctx, pick: str, money):
        cat = await self.get_cat(ctx.author)

        z = ['green', 'red', 'black']
        if not pick.lower() in z:
            return await ctx.send(ctx.lang['not_correct_choose'].format(', '.join(z)))

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)  # :)))

        if not money.isdigit():
            return await ctx.send(ctx.lang['not_correct_value'])

        money = int(money)

        if money < 5:
            return await ctx.send(ctx.lang['too_low_value'])

        if cat.money < money:
            return await ctx.send(ctx.lang['you_dont_have_so_much'])

        x = random.randint(0, 30)
        win = False
        won_money = None

        if pick.lower() == "green":
            if x == 0:
                won_money = money * 14
                win = True
            else:
                win = False
        elif pick.lower() == "black":
            if x >= 15:
                won_money = money * 2
                win = True
            else:
                win = False
        elif pick.lower() == "red":
            if x < 15:
                won_money = money * 2
                win = True
            else:
                win = False

        if win and won_money:
            msg = ctx.lang['you_won'].format(won_money, x)
            await self.bot.db.execute("UPDATE cats SET money = money + $1 WHERE owner_id = $2", won_money,
                                          ctx.author.id)
        else:
            msg = ctx.lang['you_lose'].format(x)
            await self.bot.db.execute("UPDATE cats SET money = money - $1 WHERE owner_id = $2", money,
                                          ctx.author.id)

        await ctx.send(msg)

    @commands.command()
    async def coinflip(self, ctx, money):
        """Postaw i wygraj."""
        cat = await self.get_cat(ctx.author)

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)  # :)))

        if not money.isdigit():
            return await ctx.send(ctx.lang['not_correct_value'])

        money = int(money)

        if money < 5:
            return await ctx.send(ctx.lang['too_low_value'])

        if cat.money < money:
            return await ctx.send(ctx.lang['you_dont_have_so_much'])

        x = random.randint(0, 100)

        if x == 0:
            new_money = int(money * random.randint(2, 4))
            await ctx.send(ctx.lang['you_won_jackpot'].format(f"{new_money:,d}"))
        elif x >= 50:
            new_money = int(money + money)
            await self.bot.db.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", new_money, ctx.author.id)
            await ctx.send(ctx.lang['you_won_'].format(f"{new_money:,d}"))
        else:
            new_money = int(money - money)
            await self.bot.db.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", new_money, ctx.author.id)
            await ctx.send(ctx.lang['you_lose_'].format(f"{new_money:,d}"))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slots(self, ctx, money):
        cat = await self.get_cat(ctx.author)

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)  # :)))

        if not money.isdigit():
            return await ctx.send(ctx.lang['not_correct_value'])

        money = int(money)

        if money < 5:
            return await ctx.send(ctx.lang['too_low_value'])

        if cat.money < money:
            return await ctx.send(ctx.lang['you_dont_have_so_much'])

        all_slots_icons = [icon.value for icon in SlotsEmojis]

        x1 = random.choice(all_slots_icons)
        x2 = random.choice(all_slots_icons)
        x3 = random.choice(all_slots_icons)

        z = f"{x1} | {x2} | {x3}"

        muliplier_map = {
            "\U0001f335": 1,
            "\U0001f48e": 2,
            "\U00002764": 3,
            "\U0001f496": 4,
            "\U00002b50": 5,
            "\U0001f339": 7
        }

        muliplier = (muliplier_map[x1] +
                     muliplier_map[x2] + muliplier_map[x3]) / 10

        m = muliplier * money
        won_money = round(m) - money

        if won_money < 0:
            text = ctx.lang['slots_lose'].format(z, muliplier, f"{abs(won_money):,d}")

        elif won_money == 0:
            text = ctx.lang['slots_nothing'].format(z, muliplier)

        else:
            text = ctx.lang['slots_won'].format(z, muliplier, f"{won_money:,d}")

        await ctx.send(text)
        await self.bot.db.execute("UPDATE cats SET money = money + $1 WHERE owner_id = $2", won_money,
                                  ctx.author.id)

    @commands.command()
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def trivia(self, ctx, difficulty=None):
        if difficulty not in [None, "easy", "medium", "hard"]:
            raise commands.BadArgument("Wrong difficulty passed.")

        m = await self._prepare_trivia(ctx, diff=difficulty)
        cat = await self.get_cat(ctx.author)

        won_map = {
            'easy': random.randint(50, 120),
            'medium': random.randint(150, 320),
            'hard': random.randint(400, 650)
        }

        if m[0]:

            won = won_map[m[2]]

            await ctx.send(ctx.lang['trivia_won'].format(won))
            await self.bot.db.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", cat.money + won,
                                      ctx.author.id)
        else:
            return await ctx.send(ctx.lang['trivia_lose'].format(m[1]))

    @cat.command(aliases=['inv', 'i'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def inventory(self, ctx):
        cat = await self.get_cat(ctx.author)

        inv_map = dict()

        if not cat.inventory:
            return await ctx.send(ctx.lang['empty_inventory'])

        for item in cat.inventory:
            if item not in inv_map:
                inv_map[item] = 1
            else:
                inv_map[item] += 1

        text = []

        for key, value in inv_map.items():
            text.append(f"{key} x{value}")

        fmt = '\n'.join(text)

        return await ctx.send(f"```\n{fmt}\n```")

    @cat.command(aliases=['o'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def open(self, ctx, box: ItemsConverter("box"), amount: AmountConverter = 1):
        cat = await self.get_cat(ctx.author)

        if not box:
            return await ctx.send(ctx.lang['no_box_like'])

        if not cat.inventory:
            return await ctx.send(ctx.lang['empty_inventory'])

        box = box.raw

        if box not in cat.inventory:
            return await ctx.send(ctx.lang['no_box_in_inventory'])

        all_user_boxes = len([item for item in cat.inventory if item == box])

        if amount == "all":
            amount = all_user_boxes

        amount = int(amount)

        if amount > all_user_boxes:
            return await ctx.send(ctx.lang['too_many_boxes'])

        won_items = []

        for _ in range(0, amount):
            won_item = random.choice(BOX_MAP[box])
            won_items.append('`' + won_item + '`')

            cat.inventory.append(won_item)
            cat.inventory.remove(box)

        z = '\n'.join(won_items)
        e = discord.Embed(description=f"{ctx.lang['you_opened']}:\n{z}.", color=BOX_COLOR_MAP[box])
        e.set_footer(text=ctx.author, icon_url=ctx.author.avatar_url)

        await ctx.send(embed=e)
        await self.bot.db.execute("UPDATE cats SET inventory = $1 WHERE owner_id = $2", cat.inventory, ctx.author.id)

    @cat.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def shop(self, ctx):
        cat = await self.get_cat(ctx.author)

        e = discord.Embed(description=f"{ctx.lang['balance']}: {int(cat.money):,d}$")
        e.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)

        for item in COST:
            e.add_field(name=item, value=f'{int(COST[item]):,d}$', inline=True)

        e.add_field(name='premium', value='1,5$ pp')
        e.set_footer(text=ctx.lang['buy_example'].format(ctx.prefix, random.choice([x for x in COST])))
        return await ctx.send(embed=e)

    @cat.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def buy(self, ctx, amount: typing.Optional[int] = 1, *, item: ItemsConverter("item") = None):
        cat = await self.get_cat(ctx.author)

        if not item:
            return await ctx.send(ctx.lang['no_item_like'])

        orginal_item = item

        try:
            item = COST[item]
        except KeyError:
            item = WEAPONS_PRICE.get(item)
            if not item:
                return await ctx.send(ctx.lang['no_item_like'])

        drinks_map = {
            "energy drink": "sta",
            "health drink": "hp",
            "food drink": "food"
        }

        if orginal_item in drinks_map:
            if cat.money < item:
                return await ctx.send(ctx.lang['no_money_for'].format(orginal_item, item - cat.money))

            await self.bot.db.execute(f"UPDATE cats SET {drinks_map[orginal_item]} = 100, money = $1 WHERE owner_id = $2",
                                      cat.money - item, ctx.author.id)
            return await ctx.send(ctx.lang['fuel_drink'].format(drinks_map[orginal_item]))

        if orginal_item == 'karma':
            if cat.money < item * amount:
                return await ctx.send(ctx.lang['no_money_for'].format(orginal_item, (item * amount) - cat.money))
            money = cat.money - (item * amount)
            karma = cat.karma + amount
            await self.bot.db.execute("UPDATE cats SET money = $1, karma = $2 WHERE owner_id = $3", money,
                                      karma, ctx.author.id)
            return await ctx.send(ctx.lang['bought_food'].format(amount))

        if cat.money < item * amount:
            return await ctx.send(ctx.lang['no_money_for'].format(orginal_item, (item * amount) - cat.money))

        x = await ctx.confirm(ctx.lang['confirm_buying'].format(orginal_item, amount, item * amount), ctx.author)

        if x:
            for _ in range(0, amount):
                new_balance = await cat.buy(orginal_item)
            await ctx.send(ctx.lang['bought'].format(orginal_item, amount, item * amount, new_balance))
        else:
            await ctx.send(ctx.lang['abort'])

    @cat.command(enabled=False)
    async def wear(self, ctx, *, weapon: ItemsConverter("weapon")):
        cat = await self.get_cat(ctx.author)

        if not weapon:
            return await ctx.send(ctx.lang['no_item_like'])

        if weapon.raw not in cat.inventory:
            return await ctx.send(ctx.lang['no_item_in_inventory'])

        await self.bot.db.execute("UPDATE cats SET wore_gun = $1 WHERE owner_id = $2", weapon.raw, ctx.author.id)
        await ctx.send(":ok_hand:")

    @cat.command()
    async def sell(self, ctx, *, item: ItemsConverter("item")):
        cat = await self.get_cat(ctx.author)

        if not item:
            return await ctx.send(ctx.lang['no_item_like'])

        if item not in cat.inventory:
            return await ctx.send(ctx.lang['no_item_in_inventory'])

        orginal_item = item

        try:
            item = WEAPONS_PRICE[item]
        except KeyError:
            item = COST[item]

        price = round(item / 2)
        multiplier = (item / 2) / item * 100

        x = await ctx.confirm(ctx.lang['confirm_selling'].format(orginal_item, price, multiplier),
                              ctx.author)

        if x:
            new_balance = await cat.sell(orginal_item)
            await ctx.send(ctx.lang['sold'].format(orginal_item, new_balance))
        else:
            await ctx.send(ctx.lang['abort'])

    @cat.group(invoke_without_command=True, aliases=['change'])
    async def edit(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @edit.command()
    async def name(self, ctx, *, new_name: str):
        """Zmień imię zwierzaka."""
        cat = await self.get_cat(ctx.author)

        if cat.money < 1000:
            return await ctx.send(ctx.lang['need_more_money_name'])

        new_name = new_name[:1].upper() + new_name[1:].lower()

        await self.bot.db.execute("UPDATE cats SET name = $1, money = $2 WHERE owner_id = $3", new_name,
                                  cat.money - 1000, ctx.author.id)
        await ctx.send(":ok_hand:")

    @edit.command()
    async def color(self, ctx, *, new_color: str = None):
        """Zmień kolor zwierzaka."""
        cat = await self.get_cat(ctx.author)
        if cat.money < 15000:
            return await ctx.send(ctx.lang['need_more_money_color'])

        colors = ['black', 'brown', 'grey', 'yellow', 'pink']
        premium_colors = ['gold', 'plamablue', 'plama_sea', 'plama_pretty_pink',
                          'plama_mint', 'light_green']
        if cat.premium:
            colors.extend(premium_colors)
        if await self.bot.is_owner(ctx.author):
            colors.append('owner_cat')

        if not new_color:
            return await ctx.send(ctx.lang['avalaible_colors'].format(', '.join(colors)))

        if new_color not in colors:
            return await ctx.send(ctx.lang['no_color_like_this'].format(', '.join(colors)))

        await self.bot.db.execute("UPDATE cats SET color = $1, money = $2 WHERE owner_id = $3", new_color,
                                  cat.money - 15000, ctx.author.id)
        await ctx.send(":ok_hand:")

    @edit.command()
    async def theme(self, ctx, *, new_theme: str = None):
        """Zmień tło na profilu zwierzaka."""
        cat = await self.get_cat(ctx.author)
        if cat.money < 100000:
            return await ctx.send(ctx.lang['need_more_money_theme'])

        themes = ["weed1", "weed2", "weed3", "sky3", "landscape2"]
        premium_themes = ["sky1", "sky2", "sky4", "sky5", "colors1", "jungle1", "void1", "space1", "landscape1",
                          "landscape3", "landscape4", "night_sky1"]
        if cat.premium:
            themes.extend(premium_themes)

        if not new_theme:
            return await ctx.send(ctx.lang['avalaible_themes'].format(", ".join(themes)))

        if new_theme not in themes:
            return await ctx.send(ctx.lang['no_theme_like_this'].format(", ".join(themes)))

        await self.bot.db.execute("UPDATE cats SET theme = $1, money = $3 WHERE owner_id = $2", new_theme,
                                  ctx.author.id, cat.money - 100000)
        await ctx.send(":ok_hand:")

    @cat.command()
    async def daily(self, ctx):
        await ctx.send(f"<https://discordbots.org/bot/538369596621848577/vote>, {ctx.lang['vote_pls']}")

    @cat.command()
    async def premium(self, ctx):  # $$$
        cost = 1.5
        owner = str(self.bot.get_user(self.bot.owner_id))

        e = discord.Embed(description=ctx.lang['premium_text'])
        e.set_footer(text=ctx.lang['info_premium'].format(cost, owner))

        await ctx.send(embed=e)

    @cat.command()
    async def transfer(self, ctx, member: discord.Member, amount: int):
        author = await self.get_cat(ctx.author)
        member_cat = await self.get_cat(member)

        if member.id == ctx.author.id:
            return await ctx.send(ctx.lang['cant_transfer_to_yourself'])

        if author.money < amount:
            return await ctx.send(ctx.lang['not_enough_money_transfer'])

        query_1 = "UPDATE cats SET money = money - $2 WHERE owner_id = $1"
        query_2 = "UPDATE cats SET money = money + $2 WHERE owner_id = $1"

        await self.bot.db.execute(query_1, ctx.author.id, amount)
        await self.bot.db.execute(query_2, member.id, amount)

        await ctx.send(ctx.lang['transfered_money'].format(ctx.author.mention, f"{amount:,d}", member.mention))

    # def processing_fight(self, author, enemy):
    #     path = "assets/images/battle.png"

    @cat.command()
    async def fight(self, ctx, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send(ctx.lang['cant_fight_with_yourself'])

        if member.id in self._fights:
            return await ctx.send(ctx.lang['is_already_in_fight'].format(member))

        if ctx.author.id in self._fights:
            return await ctx.send(ctx.lang['you_already_in_fight'].format(ctx.author.mention))

        author = await self.get_cat(ctx.author)
        enemy_cat = await self.get_cat(member)

        self._fights.append(member.id)
        self._fights.append(ctx.author.id)

        confirmation = await ctx.confirm(ctx.lang['confirm_fight'].format(member.mention, ctx.author.mention), member,
                                         timeout=30)
        if not confirmation:
            self._fights.remove(member.id)
            self._fights.remove(ctx.author.id)
            return await ctx.send(ctx.lang['abort'])

        default_hp = 100
        hp = round(default_hp/20) * '\U0001f7e5'

        text = f"{author.name} ({ctx.author})\n**HP**: {hp} ({(default_hp / 100) * 100}%)\n{enemy_cat.name} ({member})\n**HP:** {hp} ({(default_hp / 100) * 100}%)"

        e = discord.Embed(description=text)
        e.set_author(name=f"{ctx.author} vs {member}")
        # e.set_image(url=f"attachment://fight_{ctx.author.id}vs{member.id}.png")

        # async with ctx.typing():
        # start = time.time()
        #
        #     author_bytes = await self.get_avatar(ctx.author)
        #     enemy_bytes = await self.get_avatar(member)
        #
        #     fn = functools.partial(self.processing_fight, author_bytes, enemy_bytes)
        #     final_buffer = await self.bot.loop.run_in_executor(None, fn)
        #
        #     file = discord.File(filename=f"fight_{ctx.author.id}vs{member.id}.png", fp=final_buffer)
        #
        # end = time.time()
        # f"Done in: {round(end-start, 2)}s",

        author_weapon, enemy_weapon = await self.choose_weapon(ctx, member)

        if author_weapon is None and enemy_weapon is None:
            self._fights.remove(member.id)
            self._fights.remove(ctx.author.id)
            return await ctx.send(ctx.lang['abort'])

        class Player:
            def __init__(self, id_, weapon, hp_, member_object, cat):
                self.id = id_
                self.weapon = weapon
                self.hp = hp_
                self.member_object = member_object
                self.cat = cat

        enemy = Player(member.id, enemy_weapon, default_hp, member, enemy_cat)
        ally = Player(ctx.author.id, author_weapon, default_hp, ctx.author, author)

        winner, loser = await self.start_fight(ctx.channel, e, enemy, ally)

        query = "UPDATE cats SET rating = $1 WHERE owner_id = $2"

        rating1, rating2 = other.match(author, enemy_cat, winner.cat)

        rating1 = round(rating1)
        rating2 = round(rating2)

        await self.bot.db.execute(query, rating1, ctx.author.id)
        await self.bot.db.execute(query, rating2, member.id)

        new_rating = f"\nNowy ranking\n{ctx.author.mention}: **{rating1}**.\n{member.mention}: **{rating2}**"
        await ctx.send(ctx.lang['win_fight'].format(winner.member_object.mention, loser.member_object.mention,
                                                    new_rating))

        self._fights.remove(enemy.id)
        self._fights.remove(ally.id)

    async def choose_weapon(self, ctx, member):
        author = await self.get_cat(ctx.author)
        enemy = await self.get_cat(member)

        author_weapon = None
        enemy_weapon = None

        def author_check(m):
            return m.channel == ctx.channel and m.author == ctx.author

        def enemy_check(m):
            return m.channel == ctx.channel and m.author == member

        while author_weapon is None:
            await ctx.send(ctx.lang['choose_weapon'].format(ctx.author.mention))

            try:
                message = await self.bot.wait_for('message', check=author_check, timeout=32)
            except asyncio.TimeoutError:
                return None, None

            weapon = message.content

            if weapon.lower() in ['cancel', 'anuluj']:
                return None, None

            if weapon not in ALL_WEAPONS:
                await ctx.send(ctx.lang['no_weapon_like'])

            if weapon not in author.inventory:
                await ctx.send(ctx.lang['no_weapon_in_inv'])

            else:
                author_weapon = weapon

        while enemy_weapon is None:
            await ctx.send(ctx.lang['choose_weapon'].format(member.mention))

            try:
                message = await self.bot.wait_for('message', check=enemy_check, timeout=32)
            except asyncio.TimeoutError:
                return None, None

            weapon = message.content

            if weapon in ['cancel', 'anuluj']:
                return await ctx.send(ctx.lang['abort'])

            if weapon not in ALL_WEAPONS:
                await ctx.send(ctx.lang['no_weapon_like'])

            if weapon not in enemy.inventory:
                await ctx.send(ctx.lang['no_weapon_in_inv'])

            else:
                enemy_weapon = weapon

        return author_weapon, enemy_weapon

    @staticmethod
    async def start_fight(channel, embed, enemy, author):
        enemy_weapon = Weapon(enemy.weapon)
        ally_weapon = Weapon(author.weapon)

        message = await channel.send(embed=embed)

        round_ = 1

        while True:
            enemy_weapon.shoot(author)
            if author.hp <= 0:
                winner = enemy
                loser = author
                break

            ally_weapon.shoot(enemy)
            if enemy.hp <= 0:
                winner = author
                loser = enemy
                break

            round_ += 1

            ally_hp = math.ceil(author.hp / 20) * '\U0001f7e5'
            enemy_hp = math.ceil(enemy.hp / 20) * '\U0001f7e5'

            text = f"{author.cat.name} ({author.member_object})\n**HP**: {ally_hp} ({round((author.hp/100)*100)}%)\n{enemy.cat.name} ({enemy.member_object})\n**HP:** {enemy_hp} ({round((enemy.hp/100)*100)}%)\n\nRunda: {round_}"

            embed.description = text
            await message.edit(embed=embed)

            await asyncio.sleep(4)

        ally_hp = math.ceil(author.hp / 20) * '\U0001f7e5'
        enemy_hp = math.ceil(enemy.hp / 20) * '\U0001f7e5'

        text = f"{author.cat.name} ({author.member_object})\n**HP**: {ally_hp} ({(author.hp/100)*100}%)\n{enemy.cat.name} ({enemy.member_object})\n**HP:** {enemy_hp} ({(enemy.hp/100)*100}%)\n\nRunda: {round_}"

        embed.description = text
        await message.edit(embed=embed)

        return winner, loser

    @cat.command()
    async def revive(self, ctx):
        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", ctx.author.id)
        cat = DefaultCat(self.bot, cat)
        if not cat.is_dead:
            return await ctx.send(ctx.lang['cat_alive'])
        n_money = round(cat.money / 2)
        await self.bot.db.execute(f"UPDATE cats SET food = 10, karma = 0, sta = 15, hp = 50, is_dead = false, "
                                  f"money = $1 WHERE owner_id = $2", n_money, ctx.author.id)
        await ctx.send(ctx.lang['revive_story'].format(cat.name, ctx.author))

    @cat.command()
    async def sleep(self, ctx):
        cat = await self.get_cat(ctx.author)
        if cat.stamina == 100 and cat.is_sleeping:
            await ctx.send(ctx.lang['regenered_sta'])
            await self.bot.db.execute('UPDATE cats SET is_sleeping = false, sleeping_time = 0 WHERE owner_id = $1',
                                      ctx.author.id)
        elif cat.stamina == 100 and not cat.is_sleeping:
            return await ctx.send(ctx.lang['max_energy'])

        if cat.is_sleeping:
            await ctx.send(ctx.lang['cat_woke_up'].format(cat.sleeping_time, cat.stamina))
            await self.bot.db.execute("UPDATE cats SET is_sleeping = false, sleeping_time = 0 WHERE owner_id = $1",
                                      ctx.author.id)

        elif not cat.is_sleeping:
            await self.bot.db.execute('UPDATE cats SET is_sleeping = true, sleeping_time = 0 WHERE owner_id = $1',
                                      ctx.author.id)
            await ctx.send(ctx.lang['started_restoring'])

    @cat.command()
    @commands.cooldown(1, 1800, commands.BucketType.user)
    async def rob(self, ctx, member: discord.Member):
        robber_cat = await self.get_cat(ctx.author)
        cat = await self.get_cat(member)

        if robber_cat.money < 150:
            return await ctx.send(ctx.lang['need_more_money_to_rob'])

        ratio = random.randint(10, 45)
        robbed = random.choice([True, False])

        if robbed:
            amount = int(cat.money) * (ratio / 100)
            await self.bot.db.execute("UPDATE cats SET money = money - $1 WHERE owner_id = $2", amount, member.id)
            await self.bot.db.execute("UPDATE cats SET money = money + $1 WHERE owner_id = $2", amount, ctx.author.id)
            await ctx.send(ctx.lang['robbed'].format(ctx.author.mention, member.mention, amount))
        else:
            amount = int(robber_cat.money) * (ratio / 100)
            await self.bot.db.execute("UPDATE cats SET money = money - $1 WHERE owner_id = $2", amount, ctx.author.id)
            await ctx.send(ctx.lang['robbed_wrong'].format(ctx.author.mention, member.mention, amount))

    @cat.command(aliases=['dep'])
    async def deposit(self, ctx, money):
        cat = await self.get_cat(ctx.author)

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)  # :)))

        if not str(money).isdigit():
            return await ctx.send(ctx.lang['not_correct_value'])

        money = int(money)

        if money > cat.money:
            return await ctx.send(ctx.lang['you_dont_have_so_much'])

        await self.bot.db.execute("UPDATE cats SET bank = bank + $1, money = money - $1 WHERE owner_id = $2",
                                  money, ctx.author.id)
        await ctx.send(ctx.lang['deposited'].format(money))

    @cat.command(aliases=['with'])
    async def withdraw(self, ctx, money):
        cat = await self.get_cat(ctx.author)

        if money == "all":
            money = cat.bank

        if money == "half":
            money = round(cat.bank / 2)  # :)))

        if not str(money).isdigit():
            return await ctx.send(ctx.lang['not_correct_value'])

        money = int(money)

        if money > cat.bank:
            return await ctx.send(ctx.lang['you_dont_have_so_much'])

        await self.bot.db.execute("UPDATE cats SET bank = bank - $1, money = money + $1 WHERE owner_id = $2",
                                  money, ctx.author.id)
        await ctx.send(ctx.lang['withdrawed'].format(money))

    @cat.command(aliases=['bal', 'bank'])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author

        cat = await self.get_cat(member)

        desc = f"{member.mention}\n\tBalance: **{cat.money}$**\nBank: **{cat.bank}$**"

        e = discord.Embed(description=desc, timestamp=ctx.message.created_at, color=self.bot.color)
        await ctx.send(embed=e)

    @cat.command()
    @commands.cooldown(1, 600, commands.BucketType.user)
    async def work(self, ctx):
        plus_sentences = [ctx.lang['plus_work_1'], ctx.lang['plus_work_2']]
        minus_sentences = [ctx.lang['minus_work_1'], ctx.lang['minus_work_2']]

        choice = random.choice([True, False])

        if choice:
            amount = random.randint(55, 170)
            sentence = random.choice(plus_sentences)
            query = "UPDATE cats SET money = money + $1 WHERE owner_id = $2"
        else:
            amount = random.randint(20, 120)
            sentence = random.choice(minus_sentences)
            query = "UPDATE cats SET money = money - $1 WHERE owner_id = $2"

        await self.bot.db.execute(query, amount, ctx.author.id)
        await ctx.send(sentence.format(amount))

    @cat.command()
    @commands.cooldown(1, 9, commands.BucketType.user)
    async def top(self, ctx, sort: str = "money"):
        sorts = ['money', 'bank', 'level', 'rating']
        if sort.lower() not in sorts:
            return await ctx.send(ctx.lang['wrong_type_of_sort'].format(', '.join(sorts)))

        desc = f"**TOP {ctx.lang['for_2']} `{sort}`**\n"

        cats = await self.bot.db.fetch(f"SELECT * FROM cats ORDER BY {sort.lower()} DESC LIMIT 10")

        for i, cat in enumerate(cats):

            ads_map = {
                "money": "$",
                "bank": "$",
                "level": " level",
                "rating": " rating",
            }

            desc += f"{cat['name']} ({cat['owner_id']}): **{cat[sort.lower()]}{ads_map[sort.lower()]}**\n"

        e = discord.Embed(description=desc, color=self.bot.color)
        await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        cat = await self.bot.db.fetchrow("SELECT * FROM cats WHERE owner_id = $1", message.author.id)
        if not cat:
            return

        x = random.randint(0, 100)
        if x >= 20:
            exp = random.randint(5, 22)
            await self.bot.db.execute("UPDATE cats SET exp = $1 WHERE owner_id = $2", cat['exp'] + exp, cat['owner_id'])
        if await self.lvl_up(cat):

            language = await get_language(self.bot, message.guild)
            lang = self.bot.polish if language == "PL" else self.bot.english

            await message.channel.send(lang['level_up'].format(message.author.mention, cat.level + 1))


def setup(bot):
    bot.add_cog(Cat(bot))
