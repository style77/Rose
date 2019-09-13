import random
import asyncio
from io import BytesIO
from functools import partial
from typing import Union
import typing
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageOps
import discord
from discord.ext.commands.cooldowns import BucketType
from discord.ext import commands, tasks
from enum import Enum


class SlotsEmojis(Enum):
    CACTUS = "🌵"
    GEM = "💎"
    HEART = "❤"
    SPARKLING_HEART = "💖"
    STAR = "⭐"
    ROSE = "🌹"


class CatIsDead(commands.CommandError):
    pass


class MemberDoesNotHaveCat(commands.CommandError):
    pass


class DefaultCat(object):
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


# noinspection PyCallingNonCallable
class Cat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.losing_food.start()
        self.losing_sta.start()
        self.sleeping_restore.start()
        self.session = aiohttp.ClientSession(loop=bot.loop)
        self.rose_team = [185712375628824577, 403600724342079490]
        self.cost = {
            "karma": 1500,
            "energy drink": 12000,
            "health drink": 14000,
            "food drink": 10000,
            "premium": 5000000}

    def cog_unload(self):
        self.losing_food.cancel()
        self.losing_sta.cancel()
        self.sleeping_restore.cancel()

    async def get_cat(self, member):
        cat = await self.bot.pg_con.fetchrow("SELECT * FROM cats WHERE owner_id = $1", member.id)
        if await self.is_dead(member):
            raise CatIsDead()
        if not cat:
            raise MemberDoesNotHaveCat()
        return DefaultCat(self.bot, cat)

    async def lvl_up(self, cat: DefaultCat):
        if cat.exp > round(700 * cat.level):
            await self.bot.pg_con.execute("UPDATE cats SET level = level + 1, money = money + 65  WHERE owner_id = $1",
                                          cat.owner_id)
            return True
        else:
            return False

    async def is_dead(self, member):
        cat = await self.bot.pg_con.fetchrow("SELECT * FROM cats WHERE owner_id = $1", member.id)
        if not cat:
            return

        cat = DefaultCat(self.bot, cat)

        if cat.food <= 0:
            await self.bot.pg_con.execute("UPDATE cats SET is_dead = True, is_sleeping = False WHERE owner_id = $1",
                                          member.id)
            return True

        if cat.stamina <= 0:
            await self.bot.pg_con.execute("UPDATE cats SET is_dead = True WHERE owner_id = $1", member.id)
            return True

        if cat.health <= 0:
            await self.bot.pg_con.execute("UPDATE cats SET is_dead = True, is_sleeping = False WHERE owner_id = $1",
                                          member.id)
            return True

        if cat.is_dead:
            return True

        return False

    @tasks.loop(minutes=120)
    async def losing_food(self):
        await self.bot.pg_con.execute("UPDATE cats SET food = food - 1 WHERE food > 0")

    @tasks.loop(seconds=60)
    async def sleeping_restore(self):
        await self.bot.pg_con.execute(
            "UPDATE cats SET sta = sta + 1, sleeping_time = sleeping_time + 1 WHERE sta < 100 AND is_sleeping = TRUE AND is_dead = FALSE")

    @tasks.loop(minutes=75)
    async def losing_sta(self):
        await self.bot.pg_con.execute("UPDATE cats SET sta = sta - 1 WHERE sta > 0 AND is_sleeping = FALSE")

    @losing_food.before_loop
    async def losing_food_b4(self):
        await self.bot.wait_until_ready()

    @sleeping_restore.before_loop
    async def sleeping_b4(self):
        await self.bot.wait_until_ready()

    @losing_sta.before_loop
    async def losing_sta_b4(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def progress_bar(draw, y: int, color: tuple, progress: int):
        draw.rectangle(((41, y), (42 + (round(progress * 3.34)), y + 27)), fill=color)

    @staticmethod
    def write(image, text, cords: tuple, font, color: tuple = (0, 0, 0)):
        image.text(cords, text, fill=color, font=font)

    async def get_avatar(self, ctx, user: Union[discord.User, discord.Member]) -> bytes:
        avatar_url = user.avatar_url_as(format="png")

        async with self.session.get(str(avatar_url)) as response:
            avatar_bytes = await response.read()

        return avatar_bytes

    def processing(self, avatar_bytes: bytes, color: tuple, cat, image_path, ctx) -> BytesIO:
        with Image.open(BytesIO(avatar_bytes)) as im:
            pic = r"images/profile.png"
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
                        theme = Image.open(r"images/themes/" + theme + end)
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
                        r"images/fonts/light.otf", 45)
                    emoji_font = ImageFont.truetype(
                        r"images/fonts/emotes.otf", 45)

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
                        font=ImageFont.truetype(r"images/fonts/medium.otf", 30))

                    self.write(
                        d,
                        '{:,d}'.format(int(cat.money)),
                        (470, 254),
                        font=ImageFont.truetype(r"images/fonts/medium.otf", 30))

                    self.write(
                        d,
                        str(cat.level),
                        (460, 304),
                        font=ImageFont.truetype(r"images/fonts/medium.otf", 30))

                    if ctx.guild:
                        guild_name = ctx.guild.name
                        if len(guild_name) > 18:
                            guild_name = guild_name[:18] + "..."
                        self.write(d, guild_name, (10, 765), font=ImageFont.truetype(r"images/fonts/medium.otf", 15))

                    self.progress_bar(d, 441, (52, 152, 219), cat.stamina)
                    self.write(d, str(cat.stamina), (175, 435), font=ImageFont.truetype(
                        r"images/fonts/medium.otf", 30))
                    self.progress_bar(d, 548, (46, 204, 113), cat.food)
                    self.write(d, str(cat.food), (175, 542), font=ImageFont.truetype(
                        r"images/fonts/medium.otf", 30))
                    self.progress_bar(d, 647, (233, 30, 64), cat.health)
                    self.write(d, str(cat.health), (175, 641), font=ImageFont.truetype(
                        r"images/fonts/medium.otf", 30))
                    final_buffer = BytesIO()
                    bg.save(final_buffer, "png")

        final_buffer.seek(0)
        return final_buffer

    async def adopt_cat(self, user_id, name, color):
        await self.bot.pg_con.execute("INSERT INTO cats (owner_id, name, color) VALUES ($1, $2, $3)", user_id, name,
                                      color)

    @commands.command()
    async def adopt(self, ctx):
        """Adoptuj swojego zwierzaka"""
        cat = await self.bot.pg_con.fetchrow("SELECT * FROM cats WHERE owner_id = $1", ctx.author.id)
        if cat:
            return await ctx.send(_(ctx.lang, "Masz już kota."))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        if await self.bot.is_owner(ctx.author):
            await ctx.send(_(ctx.lang,
                             "Siema mordo, mam tu dla ciebie takiego specjalnego **FIOLETOWEGO** kotka, trzymaj!\nTeraz napisz jak chcesz go nazwać."))
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))
            name = msg.content
            name = name[:1].upper() + name[1:].lower()
            await self.adopt_cat(ctx.author.id, name, "owner_cat")
            return await ctx.send(_(ctx.lang, "Twój kot będzie nazywać się **{name}**.").format(name=name))
        kolor = random.choice(["czarnego",
                               "szarego",
                               "brązowego"])
        colors = {"czarnego": "black",
                  "szarego": "grey",
                  "brązowego": "brown"}
        await ctx.send(_(ctx.lang, "Adoptowałeś {kolor} kota! Gratulacje.\nNapisz teraz jak chcesz go nazwać.").format(
            kolor=kolor))
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=30)
        except asyncio.TimeoutError:
            return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))
        name = msg.content
        name = name[:1].upper() + name[1:].lower()
        k = colors[kolor]
        await self.adopt_cat(ctx.author.id, name, k)
        return await ctx.send(_(ctx.lang, "Twój kot będzie nazywać się **{name}**.").format(name=name))

    @commands.group(invoke_without_command=True, aliases=['profile'])
    async def cat(self, ctx, member: discord.Member = None):
        """Pokazuje profil twojego kota."""
        member = member or ctx.author
        cat = await self.get_cat(member)
        if cat.is_sleeping:
            return await ctx.send(_(ctx.lang, "Twój kot aktualnie odpoczywa."))
        if cat.is_sleeping and cat.stamina == 100:
            return await ctx.send(
                _(ctx.lang, "Twój kot aktualnie odpoczywa, lecz ma już pełno energii. Przydałoby się go obudzić."))
        kolor = cat.color
        path = r"images/cats/{}/{}.png"
        image_path = path.format(kolor, 1)

        async with ctx.typing():
            if isinstance(member, discord.Member):
                member_colour = member.colour.to_rgb()
            else:
                member_colour = (0, 0, 0)
            avatar_bytes = await self.get_avatar(ctx, member)
            fn = partial(self.processing, avatar_bytes,
                         member_colour, cat, image_path, ctx)
            final_buffer = await self.bot.loop.run_in_executor(None, fn)
            file = discord.File(filename=f"{cat.name}.png", fp=final_buffer)
            await ctx.send(file=file)

    @commands.command()
    async def roulette(self, ctx, pick: str, money=None):
        cat = await self.get_cat(ctx.author)

        z = ['green', 'red', 'black']
        if not pick.lower() in z:
            return await ctx.send(
                _(ctx.lang, "To nie jest prawidłowy wybór. Wybierz jeden z `{}`.").format(', '.join(z)))

        if not money:
            return await ctx.send(_(ctx.lang, "Musisz coś postawić."))

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)

        try:
            money = int(money)
        except ValueError:
            return await ctx.send(_(ctx.lang, "To nie jest prawidłowa liczba."))

        if money < 5:
            return await ctx.send(_(ctx.lang, "Musisz postawić więcej niż 5$."))

        if cat.money < money:
            return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))

        x = random.randint(0, 30)
        win = False

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

        if win:
            msg = _(ctx.lang, "Wygrałeś {:,d}$.\nWylosowana liczba: {}.").format(won_money, x)
            await self.bot.pg_con.execute("UPDATE cats SET money = money + $1 WHERE owner_id = $2", won_money,
                                          ctx.author.id)
        else:
            msg = _(ctx.lang, "Przegrałeś.\nWylosowana liczba: {}.").format(x)

        return await ctx.send(msg)

    @commands.command()
    async def coinflip(self, ctx, money=None):
        """Postaw i wygraj."""
        cat = await self.get_cat(ctx.author)

        if not money:
            return await ctx.send(_(ctx.lang, "Musisz coś postawić."))

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)

        try:
            money = int(money)
        except ValueError:
            return await ctx.send(_(ctx.lang, "To nie jest prawidłowa liczba."))

        if money < 5:
            return await ctx.send(_(ctx.lang, "Musisz postawić więcej niż 5$."))

        if cat.money < money:
            return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))

        x = random.randint(0, 100)

        if x == 0:
            new_money = cat.money * 2
            return await ctx.send(
                _(ctx.lang, "Wygrałeś JACKPOTA, twoje pieniądze zostały pomnożone x2.").format(new_money))
        elif x >= 50:
            new_money = cat.money + (money)
            await self.bot.pg_con.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", new_money, ctx.author.id)
            return await ctx.send(_(ctx.lang, "Wygrałeś {:,d}$.").format(money))
        else:
            new_money = cat.money - money
            await self.bot.pg_con.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", new_money, ctx.author.id)
            return await ctx.send(_(ctx.lang, "Przegrałeś.").format(new_money))

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def slots(self, ctx, money=None):
        cat = await self.get_cat(ctx.author)

        if not money:
            return await ctx.send(_(ctx.lang, "Musisz coś postawić."))

        if money == "all":
            money = cat.money

        if money == "half":
            money = round(cat.money / 2)

        try:
            money = int(money)
        except ValueError:
            return await ctx.send(_(ctx.lang, "To nie jest prawidłowa liczba."))

        if money < 5:
            return await ctx.send(_(ctx.lang, "Musisz postawić więcej niż 5$."))

        if cat.money < money:
            return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))

        all_slots_icons = [icon.value for icon in SlotsEmojis]

        x1 = random.choice(all_slots_icons)
        x2 = random.choice(all_slots_icons)
        x3 = random.choice(all_slots_icons)

        z = f"{x1} | {x2} | {x3}"

        muliplier_map = {
            "🌵": 1,
            "💎": 2,
            "❤": 3,
            "💖": 4,
            "⭐": 5,
            "🌹": 7
        }

        muliplier = (muliplier_map[x1] +
                     muliplier_map[x2] + muliplier_map[x3]) / 10

        m = muliplier * money
        won_money = round(m) - money

        text = _(ctx.lang, "{}\n\nMnożnik: {}. Wygrałeś {:,d}.").format(z, muliplier, int(won_money))

        if won_money < 0:
            text = _(ctx.lang, "{}\n\nMnożnik: {}. Przegrałeś {:,d}.").format(z, muliplier, abs(won_money))

        elif won_money == 0:
            text = _(ctx.lang, "{}\n\nMnożnik: {}. Nic nie wygrałeś.").format(z, muliplier)

        await ctx.send(text)
        await self.bot.pg_con.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", cat.money + won_money,
                                      ctx.author.id)

    @commands.command()
    async def transfer(self, ctx, member: discord.Member, money):
        if member.id == ctx.author.id:
            return await ctx.send(_(ctx.lang, "Nie możesz przelać pieniędzy samemu sobie."))
        cat = await self.get_cat(ctx.author)
        cat2 = await self.get_cat(member)

        if str(money).lower() == "all":
            money = cat.money

        if str(money).lower() == "half":
            money = round(cat.money / 2)

        try:
            money = int(money)
        except ValueError:
            return await ctx.send(_(ctx.lang, "To nie jest prawidłowa liczba."))

        if money < 5:
            return await ctx.send(_(ctx.lang, "Nie możesz przelać mniej niż 5$."))

        if money > cat.money:
            return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))

        await self.bot.pg_con.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", cat.money - money,
                                      ctx.author.id)
        await self.bot.pg_con.execute("UPDATE cats SET money = $1 WHERE owner_id = $2", cat2.money + money, member.id)

        await ctx.send(_(ctx.lang, "{}, przelał {:,d}$ {}.").format(ctx.author.mention, money, member.mention))

    @cat.command(name="adopt")
    async def adopt_(self, ctx):
        """Adoptuj swojego zwierzaka"""
        await ctx.invoke(self.bot.get_command("adopt"))

    @cat.command()
    async def raw(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        cat = await self.get_cat(member)
        if cat.is_sleeping:
            return await ctx.send(_(ctx.lang, "Twój kot aktualnie odpoczywa."))
        if cat.is_sleeping and cat.stamina == 100:
            return await ctx.send(
                _(ctx.lang, "Twój kot aktualnie odpoczywa, lecz ma już pełno energii. Przydałoby się go obudzić."))
        kolor = cat.color
        if ctx.lang == "PL":
            colors = {"black": "Czarny",
                      "grey": "Szary",
                      "brown": "Brązowy",
                      "owner_cat": "Fioletowy"}
            kolor = colors.get(kolor)
        # sorry im too lazy to translate this
        await ctx.send("""```prolog
Imie: {}
Kolor: {}
Premium: {}
Level: {} - {} exp
Pieniadze: {:,d}
HP: {}
Jedzenie: {}
Energia: {}
Ilosc Karmy: {}
guild: {}```""".format(cat.name,
                       kolor,
                       cat.premium,
                       cat.level,
                       cat.exp,
                       int(cat.money),
                       cat.health,
                       cat.food,
                       cat.food,
                       cat.karma,
                       ctx.guild.name))

    @commands.command(aliases=['bal', 'money'])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        cat = await self.get_cat(member)
        return await ctx.send(_(ctx.lang, "Masz {:,d}$.").format(int(cat.money)))

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return
        cat = await self.bot.pg_con.fetchrow("SELECT * FROM cats WHERE owner_id = $1", message.author.id)
        if not cat:
            return
        if cat['is_dead']:
            return
        cat = DefaultCat(self.bot, cat)
        if cat.is_sleeping:
            return
        x = random.randint(0, 100)
        if x >= 95:
            exp = random.randint(0, 3)
            await self.bot.pg_con.execute("UPDATE cats SET exp = $1 WHERE name = $2", cat.exp + exp, cat.name)
        if await self.lvl_up(cat):
            await message.channel.send(
                _(await get_language(self.bot, message.guild.id), "{author} twój kot osiągnął {level} poziom.").format(
                    author=message.author.mention, level=cat.level + 1))

    @cat.command()
    async def sleep(self, ctx):
        """Niech twój kot odpocznie, aby odnowić energie."""
        cat = await self.get_cat(ctx.author)
        if cat.stamina == 100 and cat.is_sleeping:
            await ctx.send(_(ctx.lang, "Twój kot zregenerował siły do pełna."))
            await self.bot.pg_con.execute('UPDATE cats SET is_sleeping = $1, sleeping_time = 0 WHERE owner_id = $2',
                                          False, ctx.author.id)
        if cat.stamina == 100 and not cat.is_sleeping:
            return await ctx.send(_(ctx.lang, "Twój kot ma już maksymalną ilość energii."))
        if cat.is_sleeping:
            await ctx.send(_(ctx.lang, "Twój kot odpoczywał **{time}**min i ma teraz **{sta}** energii.").format(
                time=cat.sleeping_time, sta=cat.stamina))
            await self.bot.pg_con.execute("UPDATE cats SET is_sleeping = $1, sleeping_time = 0 WHERE owner_id = $2",
                                          False, ctx.author.id)
        if not cat.is_sleeping:
            await self.bot.pg_con.execute('UPDATE cats SET is_sleeping = $1, sleeping_time = 0 WHERE owner_id = $2',
                                          True, ctx.author.id)
            await ctx.send(_(ctx.lang, "Twój kot teraz odpoczywa."))

    @cat.command()
    async def buy(self, ctx, amount: typing.Optional[int] = 1, *, thing: typing.Optional[str] = 'karma'):
        cat = await self.get_cat(ctx.author)
        if amount > 2147483647:
            return await ctx.send(_(ctx.lang, "Liczba musi być mniejsza od 2147483647."))
        if cat.is_sleeping:
            return await ctx.send(_(ctx.lang, "Twój kot aktualnie odpoczywa."))
        if cat.is_sleeping and cat.stamina == 100:
            return await ctx.send(
                _(ctx.lang, "Twój kot aktualnie odpoczywa, lecz ma już pełno energii. Przydałoby się go obudzić."))
        if thing in self.cost:
            if self.cost[thing] > cat.money:
                return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))
            drinks_map = {
                "energy drink": "sta",
                "health drink": "hp",
                "food drink": "food"
            }
            if thing in drinks_map:
                await self.bot.pg_con.execute(
                    f"UPDATE cats SET {drinks_map[thing]} = 100, money = $1 WHERE owner_id = $2",
                    cat.money - self.cost[thing], ctx.author.id)
                return await ctx.send(_(ctx.lang, "`{rzecz}` odnowione do pełna.").format(rzecz=drinks_map[thing]))
            if thing == 'karma':
                if cat.money < self.cost['karma'] * amount:
                    return await ctx.send(_(ctx.lang, "Nie masz tyle pieniędzy."))
                money = cat.money - (self.cost['karma'] * amount)
                karma = cat.karma + amount
                await self.bot.pg_con.execute("UPDATE cats SET money = $1, karma = $2 WHERE owner_id = $3", money,
                                              karma, ctx.author.id)
                return await ctx.send(_(ctx.lang, "Zakupiłeś **{amount}** karmy.").format(amount=amount))
            if thing == 'premium':
                if cat.premium:
                    return await ctx.send(_(ctx.lang, "Masz już premium."))
                money = cat.money - self.cost['premium']
                await self.bot.pg_con.execute("UPDATE cats SET premium = True, money = $1 WHERE owner_id = $2", money,
                                              ctx.author.id)
                return await ctx.send(":ok_hand:")
        else:
            return await ctx.send(_(ctx.lang, "Nie możesz kupić tej rzeczy."))

    @cat.command()
    async def shop(self, ctx):
        cat = await self.get_cat(ctx.author)
        z = []
        e = discord.Embed(description=_(ctx.lang, "Saldo: ") + '{:,d}'.format(int(cat.money)) + '$')
        e.set_author(name=str(ctx.author), icon_url=ctx.author.avatar_url)
        for item in self.cost:
            e.add_field(name=item, value='{:,d}'.format(int(self.cost[item])) + '$', inline=False)
        e.set_footer(
            text=_(ctx.lang, "Przykład: {}cat buy {}").format(ctx.prefix, random.choice([x for x in self.cost])))
        return await ctx.send(embed=e)

    @cat.command()
    async def feed(self, ctx):
        """Nakarm kota, aby zdobyć najedzenie."""
        cat = await self.get_cat(ctx.author)
        if cat.is_sleeping:
            return await ctx.send(_(ctx.lang, "Twój kot aktualnie odpoczywa."))
        if cat.is_sleeping and cat.sta == 100:
            return await ctx.send(
                _(ctx.lang, "Twój kot aktualnie odpoczywa, lecz ma już pełno energii. Przydałoby się go obudzić."))
        if cat.karma == 0:
            return await ctx.send(_(ctx.lang, "Nie masz żadnego jedzenia."))
        if cat.food >= 100:
            return await ctx.send(_(ctx.lang, "Twój kot ma juz maksymalną ilość jedzenia"))
        if cat.food + 15 > 100:
            await self.bot.pg_con.execute("UPDATE cats SET food = $1, karma = $2 WHERE owner_id = $3",
                                          cat.food + (100 - cat.food), cat.karma - 1, ctx.author.id)
            return await ctx.send(
                _(ctx.lang, "Nakarmiłeś kotka.\nTeraz `{name}` ma **{new_food}** jedzenia.").format(name=cat.name,
                                                                                                    new_food=cat.food + (
                                                                                                                100 - cat.food)))
        await self.bot.pg_con.execute('UPDATE cats SET food = $1, karma = $2 WHERE owner_id = $3', cat.food + 15,
                                      cat.karma - 1, ctx.author.id)
        await ctx.send(_(ctx.lang, "Nakarmiłeś kotka.\nTeraz `{name}` ma **{food}** jedzenia.").format(name=cat.name,
                                                                                                       food=cat.food + 15))

    @cat.command(aliases=['attack', 'bij_go'])
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def hit(self, ctx):
        cat = await self.get_cat(ctx.author)
        await ctx.send(_(ctx.lang, "Uderzyłeś kota, ty zwyrolu."))
        x = random.randint(1, 10)
        chances = random.randint(0, 1000)
        if chances == 1000:
            await ctx.send(_(ctx.lang, "Co ty odwaliłeś?! Za mocno!"))
            return await self.bot.pg_con.execute("UPDATE cats SET is_dead = True WHERE owner_id = $1", ctx.author.id)
        return await self.bot.pg_con.execute("UPDATE cats SET hp = $2 WHERE owner_id = $1", ctx.author.id,
                                             cat.health - x)

    @cat.command()
    async def revive(self, ctx):
        """Jeśli twój zwierzak zmarł możesz go odrodzić."""
        cat = await self.bot.pg_con.fetchrow("SELECT * FROM cats WHERE owner_id = $1", ctx.author.id)
        if not cat['is_dead']:
            return await ctx.send(_(ctx.lang, "Twój kot żyje."))
        n_money = round(cat['money'] / 2)
        await self.bot.pg_con.execute(
            f"UPDATE cats SET food = 10, karma = 0, sta = 15, hp = 50, is_dead = $1, money = $2 WHERE owner_id = $3",
            False, n_money, ctx.author.id)
        await ctx.send(_(ctx.lang,
                         "**{name}** *nagle powstał z martwych jako kot widmo i przeteleportował się pod okno* **{author}** *jego złego pana, tak naprawdę nikt nie wie czemu do niego wrócił, ale kogo to obchodzi.*").format(
            name=cat['name'], author=ctx.author))

    @cat.command(aliases=['p'])
    @commands.cooldown(1, 10800, BucketType.user)
    async def play(self, ctx):
        """Pobaw się z zwierzakiem."""
        try:
            cat = await self.get_cat(ctx.author)
        except Exception as e:
            return self.bot.get_command('cat play').reset_cooldown(ctx)
        if cat.is_sleeping:
            await ctx.send(_(ctx.lang, "Twój kot aktualnie odpoczywa."))
            return self.bot.get_command('cat play').reset_cooldown(ctx)
        if cat.is_sleeping and cat.stamina == 100:
            await ctx.send(
                _(ctx.lang, "Twój kot aktualnie odpoczywa, lecz ma już pełno energii. Przydałoby się go obudzić."))
            return self.bot.get_command('cat play').reset_cooldown(ctx)
        if cat.stamina < 7 or cat.food < 12:
            await ctx.send(_(ctx.lang, "Twój kot jest zbyt zmęczony lub głodny."))
            return self.bot.get_command('cat play').reset_cooldown(ctx)
        async with ctx.typing():
            await asyncio.sleep(10)
            exp = random.randint(1, 15)
            await ctx.send(
                _(ctx.lang, "Bawiłeś się z `{name}`.\nZdobyłeś **{exp}** expa.").format(name=cat.name, exp=exp))
            await self.bot.pg_con.execute("UPDATE cats SET exp = $1, sta = $2, food = $3 WHERE owner_id = $4",
                                          cat.exp + exp, cat.stamina - 5, cat.food - 8, ctx.author.id)
            if await self.lvl_up(cat):
                await ctx.send(
                    _(ctx.lang, "{author} twój kot osiągnął **{level}** level.").format(author=ctx.author.mention,
                                                                                        level=cat.level + 1))

    @cat.group(invoke_without_command=True)
    async def edit(self, ctx):
        z = []
        for cmd in self.bot.get_command("cat edit").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz ustawić:\n```\n{}```").format('\n'.join(z)))

    @edit.command()
    async def name(self, ctx, *, new_name: str):
        """Zmień imię zwierzaka."""
        cat = await self.get_cat(ctx.author)

        if cat.money < 15000:
            return await ctx.send(_(ctx.lang, "Nie masz wystarczająco pieniędzy na zmiane imienia zwierzaka."))

        new_name = new_name[:1].upper() + new_name[1:].lower()

        await self.bot.pg_con.execute("UPDATE cats SET name = $1, money = $2 WHERE owner_id = $3", new_name,
                                      cat.money - 15000, ctx.author.id)
        await ctx.send(":ok_hand:")

    @edit.command()
    async def color(self, ctx, *, new_color: str = None):
        """Zmień kolor zwierzaka."""
        cat = await self.get_cat(ctx.author)
        if cat.money < 25000:
            return await ctx.send(_(ctx.lang, "Nie masz wystarczająco pieniędzy na zmiane koloru zwierzaka."))

        colors = ['black', 'brown', 'grey']
        vip_colors = ['gold', 'plamablue', 'yellow', 'pink', 'plama_sea', 'plama_pretty_pink',
                      'plama_mint', 'light_green']
        if cat.premium:
            colors.extend(vip_colors)
        if await self.bot.is_owner(ctx.author):
            colors.append('owner_cat')

        if not new_color:
            return await ctx.send(_(ctx.lang, "Dostępne kolory `{}`.").format(', '.join(colors)))

        if new_color not in colors:
            return await ctx.send(_(ctx.lang, "Nie ma takiego koloru. Spróbuj jeden z `{}`.").format(', '.join(colors)))

        await self.bot.pg_con.execute("UPDATE cats SET color = $1, money = $2 WHERE owner_id = $3", new_color,
                                      cat.money - 25000, ctx.author.id)
        await ctx.send(":ok_hand:")

    @edit.command()
    async def theme(self, ctx, *, new_theme: str = None):
        """Zmień tło na profilu zwierzaka."""
        cat = await self.get_cat(ctx.author)
        if cat.money < 100000:
            return await ctx.send(_(ctx.lang, "Nie masz wystarczająco pieniędzy na zmiane tła na profilu."))

        themes = ["weed1", "weed2", "weed3"]
        vip_themes = ["sky1", "sky2", "sky3", "sky4", "sky5", "colors1", "jungle1", "void1", "space1", "landscape1",
                      "landscape2", "landscape3", "landscape4", "night_sky1"]
        if cat.premium:
            themes.extend(vip_themes)

        if not new_theme:
            return await ctx.send(_(ctx.lang, "Dostępne tła `{}`.").format(", ".join(themes)))

        if new_theme not in themes:
            return await ctx.send(_(ctx.lang, "Nie ma takiego tła. Spróbuj jedno z `{}`.").format(", ".join(themes)))

        await self.bot.pg_con.execute("UPDATE cats SET theme = $1, money = $3 WHERE owner_id = $2", new_theme,
                                      ctx.author.id, cat.money - 100000)
        await ctx.send(":ok_hand:")

    @commands.command()
    async def daily(self, ctx):
        return await ctx.send(_(ctx.lang,
                                "<https://discordbots.org/bot/538369596621848577/vote>, zagłosuj a za pare chwil dostaniesz nagrodę!"))


def setup(bot):
    bot.add_cog(Cat(bot))
