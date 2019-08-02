import asyncio
import random
import re
import traceback
import typing

import aiohttp
import discord
from discord.ext import commands, tasks
from discord.ext.commands.cooldowns import BucketType

from cogs.classes.converters import EasyOneDayTime, ModerationReason, TrueFalseConverter, TrueFalseError, BannedMember
from cogs.classes.plugin import Plugin
from cogs.classes import cache
from cogs.music import add_react
from cogs.utils import settings
from cogs.utils import utils

invite_regex = re.compile(r"(?:https?://)?discord(?:app\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")
link_regex = re.compile(
    r"((http(s)?(\:\/\/))+(www\.)?([\w\-\.\/])*(\.[a-zA-Z]{2,3}\/?))[^\s\b\n|]*[^.,;:\?\!\@\^\$ -]")

class NewGuild(Exception):
    pass

class EmojiCensor:
    emoji_dict = dict(shit=':poop:',
                      gowno=':poop:',
                      gówno=':poop:',
                      fuck=':dolphin:',
                      japierdole=':dolphin:',
                      pierdole=':dolphin:',
                      kurwa=':dolphin:',
                      jebać=':dolphin:',
                      jebac=':dolphin:',
                      suka=':sunglasses:',
                      dupek=':peach:',
                      pizda=':peach:',
                      cipa=':peach:',
                      szmata=':dog:',
                      nigger=':monkey:',
                      czarnuch=':monkey:',
                      pedal=':bike:',
                      pedał=':bike:',
                      chuj=':hatched_chick:',
                      kutas=':hatched_chick:',
                      pussy=':cat:',
                      )

    def emojiInterpreter(self, word):
        if word in EmojiCensor.emoji_dict:
            return EmojiCensor.emoji_dict[word]
        else:
            return None

class Plugins(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @check_permissions(manage_guild=True)
    async def plugin(self, ctx):
        z = []
        for cmd in self.bot.get_command("plugin").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Komendy w tej grupie:\n```\n{}```").format('\n'.join(z)))

    @plugin.command(aliases=['on'])
    @check_permissions(manage_guild=True)
    async def enable(self, ctx, module: str):
        cog = self.bot.get_cog(module)
        cant_off_modules = ['plugins']

        if not cog or module.lower() in cant_off_modules:
            return await ctx.send(_(ctx.lang, "Nie ma takiego modułu, bądź nie jest on możliwy do włączenia."))

        await cog.turn_on(ctx.bot.pg_con, ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @plugin.command(aliases=['off'])
    @check_permissions(manage_guild=True)
    async def disable(self, ctx, module: str):
        cog = self.bot.get_cog(module)
        cant_off_modules = ['plugins']

        if not cog or module.lower() in cant_off_modules:
            return await ctx.send(_(ctx.lang, "Nie ma takiego modułu, bądź nie jest on możliwy do wyłączenia."))

        await cog.turn_off(ctx.bot.pg_con, ctx.guild.id)
        return await ctx.send(":ok_hand:")

class Settings(Plugin):
    """
        Komendy moderacyjne. Bardzo wiele opcji dostosowania serwera do swoich potrzeb.
         Jeśli potrzebujesz pomocy sprobuj komendy /support.
    """

    def __init__(self, bot):
        self.bot = bot
        self.msgs = {}
        self.youtube_key = utils.get_from_config('yt_key')
        self.update_subs.start()

    async def update_cache(self, guild):
        cache_get = cache.GuildSettingsCache().get(guild.id)
        if not cache_get:
            z = await self.bot.pg_con.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild.id)
            cache.GuildSettingsCache().update(guild, "database", z)

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        else:
            return True

    def cog_unload(self):
        self.update_subs.cancel()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def block(self, ctx, user: discord.User = None, *, reason: str = 'Brak powodu'):
        """Blokuje użytkownikowi dostęp do komend bota."""
        blocked_members = await self.bot.pg_con.fetchrow("SELECT * FROM blacklist WHERE user_id = $1", user.id)
        if blocked_members:
            return await ctx.send(_(ctx.lang, "Ta osoba jest już w blackliście."))
        await self.bot.pg_con.execute("INSERT INTO blacklist (user_id, reason) VALUES ($1, $2)", user.id, reason)
        return await ctx.send(_(ctx.lang, "Dodano {} do blacklisty.").format(user.mention))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def unblock(self, ctx, user: discord.User = None):
        blocked_members = await self.bot.pg_con.fetchrow("SELECT * FROM blacklist WHERE user_id = $1", user.id)
        if not blocked_members:
            return await ctx.send(_(ctx.lang, "Ta osoba nie jest w blackliście."))
        await self.bot.pg_con.execute("DELETE FROM blacklist WHERE user_id = $1", user.id)
        return await ctx.send(_(ctx.lang, "Usunięto {} z blacklisty.").format(user.mention))

    @tasks.loop(minutes=5)
    async def update_subs(self):
        try:
            subs = await self.bot.pg_con.fetch("SELECT * FROM youtube_stats")
            for sub in subs:
                name = sub['name']
                async with aiohttp.ClientSession() as cs:
                    async with cs.get(
                            f"https://www.googleapis.com/youtube/v3/channels?part=statistics&forUsername={name}&key={self.youtube_key}") as r:
                        res = await r.json()
                        try:
                            new_subs = res["items"][0]["statistics"]["subscriberCount"]
                            new_subs = "{}: {:,d}.".format(name, int(new_subs))
                        except IndexError:
                            new_subs = "channel not found."
                        except KeyError as e:
                            print(res)
                            return
                channel = self.bot.get_channel(sub['channel_id'])
                if not channel:
                    await self.bot.pg_con.execute("DELETE FROM youtube_stats WHERE channel_id = $1", sub['channel_id'])
                await channel.edit(name=new_subs)
        except Exception as e:
            traceback.print_exc()

    @update_subs.before_loop
    async def update_subs_b4(self):
        await self.bot.wait_until_ready()

    @commands.group(name="youtube", invoke_without_command=True, aliases=['yt'])
    @check_permissions(manage_guild=True)
    async def youtube_(self, ctx):
        z = []
        for cmd in self.bot.get_command("youtube").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Komendy w tej grupie:\n```\n{}```").format('\n'.join(z)))

    @youtube_.command(name="add")
    @check_permissions(manage_guild=True)
    async def add_(self, ctx, channel: discord.VoiceChannel = None, *, channel_name=None):
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if not member:
            return await ctx.send(_(ctx.lang, "{}, nie posiadasz konta premium.").format(ctx.author.mention))
        if len(member[0]['youtube_stats']) + 1 >= member[0]['stats_limit']:
            return await ctx.send(_(ctx.lang, "{}, nie możesz już dodawać statystyk.").format(ctx.author.mention))
        elif channel.id in member[0]['youtube_stats']:
            return await ctx.send(_(ctx.lang, "Ten kanał już jest używany jako licznik subskrybcji."))
        await self.bot.pg_con.execute("INSERT INTO youtube_stats(guild_id, channel_id, name) VALUES ($1, $2, $3)",
                                      ctx.guild.id, channel.id, channel_name)
        member[0]['youtube_stats'].append(channel.id)
        await self.bot.pg_con.execute("UPDATE members SET youtube_stats = $1 WHERE id = $2", member[0]['youtube_stats'],
                                      ctx.author.id)
        await ctx.send(_(ctx.lang, ":ok_hand:, pamiętaj jeśli ten kanał nie istnieje to nic tutaj nie zadziała."))

    @youtube_.command(name="edit")
    @check_permissions(manage_guild=True)
    async def edit_(self, ctx, channel: discord.VoiceChannel = None, *, channel_name=None):
        chan = await self.bot.pg_con.fetch("SELECT * FROM youtube_stats WHERE channel_id = $1", channel.id)
        if not chan:
            return await ctx.send(_(ctx.lang, "Ten kanał nie posiada statystyk subskrybcji."))
        await self.bot.pg_con.execute("UPDATE youtube_stats SET name = $1 WHERE channel_id = $2", channel_name,
                                      channel.id)
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if not member:
            return await ctx.send(_(ctx.lang, "{}, nie posiadasz konta premium.").format(ctx.author.mention))
        elif channel.id in member[0]['youtube_stats']:
            return await ctx.send(_(ctx.lang, "Ten kanał już jest używany jako licznik subskrybcji."))
        member[0]['youtube_stats'].append(channel.id)
        await self.bot.pg_con.execute("UPDATE members SET youtube_stats = $1 WHERE id = $2", member[0]['youtube_stats'],
                                      ctx.author.id)
        await ctx.send(":ok_hand:")

    @youtube_.command(name="remove", aliases=['delete'])
    @check_permissions(manage_guild=True)
    async def remove_(self, ctx, channel: discord.VoiceChannel = None):
        chan = await self.bot.pg_con.fetch("SELECT * FROM youtube_stats WHERE channel_id = $1", channel.id)
        if not chan:
            return await ctx.send(_(ctx.lang, "Ten kanał nie posiada statystyk subskrybcji."))
        await self.bot.pg_con.execute("DELETE FROM youtube_stats WHERE channel_id = $1", channel.id)
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if channel.id in member[0]['youtube_stats']:
            member[0]['youtube_stats'].pop(channel.id)
            await self.bot.pg_con.execute("UPDATE members SET youtube_stats = $1 WHERE id = $2",
                                          member[0]['youtube_stats'], ctx.author.id)
        await ctx.send(":ok_hand:")
        await channel.delete()

    @youtube_.command(hidden=True)
    @commands.is_owner()
    async def limit(self, ctx, member: discord.Member = None, number: int = None):
        member = await self.bot.pg_con.fetch("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if not member:
            return await ctx.send(_(ctx.lang, "{}, nie posiada konta premium.").format(ctx.author))
        await self.bot.pg_con.execute("UPDATE members SET stats_limit = $1 WHERE id = $2", number, member.id)
        return await ctx.send(":ok_hand:")

    @commands.group(invoke_without_command=True, hidden=True)
    @commands.is_owner()
    async def sql(self, ctx):
        z = []
        for cmd in self.bot.get_command("sql").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Komendy w tej grupie:\n```\n{}```").format('\n'.join(z)))

    @sql.command(hidden=True)
    @commands.is_owner()
    async def execute(self, ctx, *, query=None):
        query = query.replace("```", "")
        if "_author.id" in query:
            query = query.replace("_author.id", str(ctx.author.id))
        if "_guild.id" in query:
            query = query.replace("_guild.id", str(ctx.guild.id))
        try:
            e = await self.bot.pg_con.execute(query)
        except Exception as er:
            e = f"{type(er)} - {er}"
        await ctx.send(e)

    @sql.command(hidden=True)
    @commands.is_owner()
    async def fetch(self, ctx, *, query=None):
        query = query.replace("```", "")
        if "_author.id" in query:
            query = query.replace("_author.id", str(ctx.author.id))
        if "_guild.id" in query:
            query = query.replace("_guild.id", str(ctx.guild.id))
        try:
            e = await self.bot.pg_con.fetch(query)
        except Exception as er:
            e = f"{type(er)} - {er}"
        z = []
        for x in e:
            z.append(str(x))
        paginator = commands.Paginator()
        for line in z:
            paginator.add_line(line)

        for page in paginator.pages:
            await ctx.send(page)

    @commands.Cog.listener()
    async def on_message(self, m):
        ctx = await self.bot.get_context(m)
        pre = await utils.get_pre(self.bot, m)
        if m.content.lower() in ["<@538369596621848577>", "<@!538369596621848577>"]:
            if not m.guild:
                return m.author.send(
                    "Nie musisz używać prefixu w prywatnych wiadomościach.\nYou don't have to use prefix in dms")
            return await m.channel.send(
                _(await get_language(self.bot, m.guild.id), "Prefix dla tego serwera to: `{}`.").format(pre[0]))

        if ctx.prefix is not None:
            p = self.bot.get_command(m.content.lower().replace(ctx.prefix, ""))
            if p is not None:
                return

        if m.guild and not m.author.bot:
            guild = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", m.guild.id)
            if guild:
                global_emojis = guild[0]['global_emojis']
                blacklist = guild[0]['blacklist']
                invite_blocker = guild[0]['invite_blocker']
                emoji_censor = guild[0]['emoji_censor']
                anti_raid = guild[0]['anti_raid']
                anti_link = guild[0]['anti_link']

                emoji_re = re.compile(r"(;\w+;)")

                msg_search_for_emote = re.findall(emoji_re, m.content.lower())
                if global_emojis and msg_search_for_emote:
                    i = 0
                    emotes = []
                    for d in msg_search_for_emote:
                        rest = str(d).replace(";", "")

                        i += 1

                        found_emojis = [emoji for emoji in ctx.bot.emojis
                                        if emoji.name.lower() == rest and emoji.require_colons]
                        if found_emojis:
                            emoji = str(random.choice(found_emojis))
                            emotes.append(emoji)
                        else:
                            return

                    await m.channel.send(' '.join(emotes))
                mc = m.content.lower()  # await commands.clean_content().convert(ctx, m.content.lower())
                if mc in blacklist and m.author.guild_permissions.administrator == False:
                    await m.channel.send(settings.replace_with_args(guild['blacklist_warn'], m.author))
                    ctx.author = self.bot.user
                    await ctx.invoke(self.bot.get_command("warn add"), member=m.author, reason="Blacklist")
                    try:
                        await m.delete()
                    except discord.Forbidden:
                        raise commands.BotMissingPermissions(["manage_messages"])
                if invite_blocker and m.author.guild_permissions.administrator == False:
                    if m.author == self.bot.user:
                        return
                    match = re.findall(invite_regex, mc)
                    if match:
                        await m.channel.send(
                            _(ctx.lang, "{author}, reklamowanie innych serwerów jest tutaj zabronione.").format(
                                author=m.author.mention))
                        ctx.author = self.bot.user
                        await ctx.invoke(self.bot.get_command("warn add"), member=m.author, reason="Invite blocker")
                        try:
                            await m.delete()
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(["manage_messages"])
                        finally:
                            return

                if emoji_censor and m.author.guild_permissions.administrator == False:
                    if m.author == self.bot.user:
                        return

                    new_cont = self.replace_bad_words(mc.split())

                    if new_cont is not None:
                        try:
                            await m.delete()
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(["manage_messages"])
                        await m.channel.send("{}: {}".format(m.author.mention, new_cont))

                if anti_raid and m.author.guild_permissions.administrator == False:
                    if m.content is None and m.attachments:
                        return
                    if m.content.lower() in ["@everyone", "@here"]:
                        ctx.author = self.bot.user
                        await ctx.invoke(self.bot.get_command("warn add"), member=m.author, reason="Anti raid")
                        try:
                            await m.delete()
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(["manage_messages"])
                    if m.content.startswith(("?", "!", ".", "+", "/", "$", "%", "!!", "t!", "p!", "~", ">", "-", ">>",
                                             "pls", "++", "$$", "\\", ":", "..", "//", "´", ",", ";")):
                        return
                    if m.author.id in self.msgs:
                        if self.msgs[m.author.id]['content'] == m.content.lower():
                            self.msgs[m.author.id]['count'] += 1
                            if self.msgs[m.author.id]['count'] >= 2:
                                ctx.author = self.bot.user
                                await ctx.invoke(self.bot.get_command("warn add"), member=m.author, reason="Anti raid")
                                self.msgs.pop(m.author.id)
                        else:
                            self.msgs.pop(m.author.id)
                    else:
                        self.msgs[m.author.id] = {}
                        self.msgs[m.author.id]['content'] = m.content.lower()
                        self.msgs[m.author.id]['count'] = 0
                if anti_link and m.author.guild_permissions.administrator == False:
                    if m.author == self.bot.user:
                        return
                    match = re.findall(link_regex, mc)
                    if match:
                        await m.channel.send(_(ctx.lang, "{author}, wysyłanie linków jest tutaj zabronione.").format(
                            author=m.author.mention))
                        ctx.author = self.bot.user
                        await ctx.invoke(self.bot.get_command("warn add"), member=m.author, reason="Anti link")
                        try:
                            await m.delete()
                        except discord.Forbidden:
                            raise commands.BotMissingPermissions(["manage_messages"])

    def replace_bad_words(self, mc):
        safe_words = []
        for word in mc:
            if word in EmojiCensor().emoji_dict:
                word = word.replace(
                    word, EmojiCensor().emojiInterpreter(word))
            safe_words.append(word)
        if mc != safe_words:
            return ' '.join(safe_words)
        return None

    @commands.command()
    @check_permissions(manage_guild=True)
    async def prefix(self, ctx, *, new_prefix: str = None):
        pref = await self.bot.pg_con.fetch("SELECT * FROM prefixes WHERE guild_id = $1", ctx.guild.id)
        if not new_prefix:
            if pref:
                prefix = pref[0]['prefix']
            else:
                prefix = '/'
            return await ctx.send(_(ctx.lang, "Prefix dla tego serwera to: `{}`.").format(prefix))
        if not pref:
            await self.bot.pg_con.execute(
                "INSERT INTO prefixes (guild_id, prefix) VALUES ($1, $2)",
                ctx.guild.id, new_prefix)
            await ctx.send(_(ctx.lang, "Nowy prefix to `{new_prefix}`").format(new_prefix=new_prefix))
        elif pref:
            await self.bot.pg_con.execute(
                "UPDATE prefixes SET prefix = $1 WHERE guild_id = $2",
                new_prefix, ctx.guild.id)
            await ctx.send(_(ctx.lang, "Nowy prefix to `{new_prefix}`").format(new_prefix=new_prefix))

    @commands.command(hidden=True)
    @commands.is_owner()
    async def invoke(self, ctx, name: str = None):
        """Wywołaj komende bez cooldowna."""
        await ctx.invoke(self.bot.get_command(name))

    @commands.command()
    @check_permissions(manage_guild=True)
    async def settings(self, ctx):
        guild = await settings.get_guild_settings(ctx, ctx.guild.id)
        if not guild:
            return await ctx.send(_(ctx.lang, "Nic nie ustawiono na tym serwerze."))
        e = discord.Embed(
            description=_(ctx.lang, "Ustawienia dla **{}**").format(ctx.guild.name))

        all_settings = ['stars_count', 'heartboard', 'welcomer_channel',
                        'welcome_text', 'self_starring', 'global_emojis',
                        'invite_blocker', 'emoji_censor', 'warns_kick',
                        'anti_raid', 'anti_link', 'auto_role']

        for data in all_settings:
            value = guild[data]
            if data in ['heartboard', 'welcomer_channel']:
                if value is not None:
                    value = self.bot.get_channel(value).mention
            elif data in ['auto_role']:
                if value is not None:
                    value = ctx.guild.get_role(value).mention
            if value is not None:
                e.add_field(name=data, value=value, inline=False)
        e.set_footer(text=_(ctx.lang, "Język: {}").format(guild['lang']))
        return await ctx.send(embed=e)

    @commands.command()
    @check_permissions(manage_guild=True)
    async def setup(self, ctx):
        """Jeśli zdecydujesz się na to, gdy server jest ustawiony, to wszystkie opcje zostaną zresetowane. Po odpisaniu 'tak' nie ma odwrotu."""
        await ctx.send(_(ctx.lang, "Na pewno? Odpisz `tak`."))

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        lang = ctx.lang
        try:
            msg = await self.bot.wait_for('message', check=check, timeout=40)
        except asyncio.TimeoutError:
            return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))
        if msg.content.lower() in ["tak", "yes"]:
            await self.bot.pg_con.execute("DELETE FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(_(lang,
                             "Więc zaczynamy.\nJeśli nie będziesz chciał czegoś ustawiać zamiast oznaczania kanały bądź wpisywania `make`, wpisz `None`.\nOznacz kanał jakim ma być `heartboard` albo wpisz `make`, aby stworzyć kanał."))
            msg1 = await self.bot.wait_for('message', check=check)
            channel1 = None
            if msg1.content.lower() == 'make':
                channel1 = await ctx.guild.create_text_channel('heartboard')
                ch = channel1.id
            elif msg1.content.lower() == 'none':
                ch = None
            else:
                channel1 = await commands.TextChannelConverter().convert(ctx, msg1.content)
                ch = channel1.id
            await self.bot.pg_con.execute("INSERT INTO guild_settings (heartboard, guild_id) VALUES ($1, $2)", ch,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            await ctx.send(_(lang, "Oznacz kanał jakim ma być `welcomer` albo wpisz `make`, aby stworzyć kanał."))
            msg2 = await self.bot.wait_for('message', check=check)
            if msg2.content.lower() == 'make':
                channel2 = await ctx.guild.create_text_channel('welcomer')
                ch2 = channel2.id
            elif msg2.content.lower() == 'none':
                ch2 = None
            else:
                channel2 = await commands.TextChannelConverter().convert(ctx, msg2.content)
                ch2 = channel2.id
            await self.bot.pg_con.execute("INSERT INTO guild_settings (welcomer_channel, guild_id) VALUES ($1, $2)",
                                          ch2, ctx.guild.id)
            await ctx.send(_(lang,
                             "Teraz ustawimy tekst powitalny.\nDodatkowe argumenty:\n```\n<@USER> - oznaczenie usera\n<USER> - nazwa usera\n<GUILD> - nazwa serwera\n\nReszte znajdziesz w dokumentacji - style77.github.io```"))

            msg3 = await self.bot.wait_for('message', check=check)
            text = msg3.content
            if text.lower() == 'none':
                text = None
            await self.bot.pg_con.execute("INSERT INTO guild_settings (welcome_text, guild_id) VALUES ($1, $2)", text,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            if ch is not None:
                await ctx.send(_(lang, "Zezwalasz na `self_starring`? Odpowiedz `True` lub `False`."))
                msgg = await self.bot.wait_for('message', check=check)
                if msgg.content.lower() in ['true', '1', 'enable']:
                    answer = True
                elif msgg.content.lower() in ['false', '0', 'disable']:
                    answer = False
                else:
                    await ctx.send(_(lang, "To nie jest prawidłowa odpowiedź. Ustawiam `False`."))
                    answer = False
                await self.bot.pg_con.execute("UPDATE guild_settings SET self_starring = $1 WHERE guild_id = $2",
                                              answer, ctx.guild.id)
                await ctx.send(':ok_hand:')

            await ctx.send(_(lang, "Czy chcesz włączyć `invite_blocker`? Odpowiedz `True` lub `False`."))
            msgg = await self.bot.wait_for('message', check=check)
            if msgg.content.lower() in ['true', '1', 'enable']:
                answer = True
            elif msgg.content.lower() in ['false', '0', 'disable']:
                answer = False
            else:
                await ctx.send(_(lang, "To nie jest prawidłowa odpowiedź. Ustawiam `False`."))
                answer = False
            await self.bot.pg_con.execute("UPDATE guild_settings SET invite_blocker = $1 WHERE guild_id = $2", answer,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            await ctx.send(_(lang, "Czy chcesz włączyć `emoji_censor`? Odpowiedz `True` lub `False`."))
            msgg = await self.bot.wait_for('message', check=check)
            if msgg.content.lower() in ['true', '1', 'enable']:
                answer = True
            elif msgg.content.lower() in ['false', '0', 'disable']:
                answer = False
            else:
                await ctx.send(_(lang, "To nie jest prawidłowa odpowiedź. Ustawiam `False`."))
                answer = False
            await self.bot.pg_con.execute("UPDATE guild_settings SET emoji_censor = $1 WHERE guild_id = $2", answer,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            await ctx.send(_(lang, "Czy chcesz włączyć `anti_raid`? Odpowiedz `True` lub `False`."))
            msgg = await self.bot.wait_for('message', check=check)
            if msgg.content.lower() in ['true', '1', 'enable']:
                answer = True
            elif msgg.content.lower() in ['false', '0', 'disable']:
                answer = False
            else:
                await ctx.send(_(lang, "To nie jest prawidłowa odpowiedź. Ustawiam `False`."))
                answer = False
            await self.bot.pg_con.execute("UPDATE guild_settings SET anti_raid = $1 WHERE guild_id = $2", answer,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            await ctx.send(_(lang, "Czy chcesz włączyć `anti_link`? Odpowiedz `True` lub `False`."))
            msgg = await self.bot.wait_for('message', check=check)
            if msgg.content.lower() in ['true', '1', 'enable']:
                answer = True
            elif msgg.content.lower() in ['false', '0', 'disable']:
                answer = False
            else:
                await ctx.send(_(lang, "To nie jest prawidłowa odpowiedź. Ustawiam `False`."))
                answer = False
            await self.bot.pg_con.execute("UPDATE guild_settings SET anti_link = $1 WHERE guild_id = $2", answer,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

            if channel1 is not None:
                await ctx.send(_(lang, "Ile ma być reakcji pod wiadomością, aby pojawiła się na `heartboardzie`?"))
                msgg = await self.bot.wait_for('message', check=check)
                if str(msgg.content).isdigit():
                    await self.bot.pg_con.execute("UPDATE guild_settings SET stars_count = $1 WHERE guild_id = $2",
                                                  int(msgg.content), ctx.guild.id)
                else:
                    await ctx.send(_(lang,
                                     "To nie jest prawidłowa liczba.\nSprawdź czy dobrze wpisałeś liczbę,"
                                     " jeśli błąd dalej będzie się powtarzał zgłoś go na serwerze do "
                                     "pomocy `{}support`.").format(ctx.prefix))

            await ctx.send(_(lang, "Oznacz rangę jaka ma być przyznawana nowym użytkownikom tego serwera."))
            msg = await self.bot.wait_for('message', check=check)
            if msg.content.lower() == 'none':
                role = None
            else:
                role = await commands.RoleConverter().convert(ctx, msg.content)
                if not role:
                    role = None
                    await ctx.send(_(lang,
                                     "Wystąpił problem z przekonwertowaniem roli.\nSprawdź poprawność nazwy/id, "
                                     "a jeśli ją oznaczyłeś zgłoś błąd na serwerze do pomocy `{}support`.").format(
                        ctx.prefix))
                role = role.id
            await self.bot.pg_con.execute("UPDATE guild_settings SET auto_role = $1 WHERE guild_id = $2", role,
                                          ctx.guild.id)

            await ctx.send('Zezwalasz na `global_emojis`? Odpowiedz `True` lub `False`')
            msgg = await self.bot.wait_for('message', check=check)
            if msgg.content.lower() in ['true', '1', 'enable']:
                answer = True
            elif msgg.content.lower() in ['false', '0', 'disable']:
                answer = False
            await self.bot.pg_con.execute("UPDATE guild_settings SET global_emojis = $1 WHERE guild_id = $2", answer,
                                          ctx.guild.id)

            # await ctx.send('Zezwalasz na `levels`? Odpowiedz `True` lub `False`')
            # msgg = await self.bot.wait_for('message', check=check)
            # if msgg.content.lower() in ['true', '1', 'enable']:
            #     answer = True
            # elif msgg.content.lower() in ['false', '0', 'disable']:
            #     answer = False
            # await self.bot.pg_con.execute("UPDATE guild_settings SET levels = $1 WHERE guild_id = $2", answer, ctx.guild.id)

            await ctx.send(_(lang,
                             ":ok_hand:\nZakończono ustawianie serwera.\nAby ustawić blacklistę wyrazów "
                             "sprawdz komende `{}set blacklist`.").format(
                ctx.prefix))
        else:
            return await ctx.send(_(lang, "Anulowano ustawianie serwera."))

    @commands.group(name="set", invoke_without_command=True)
    @check_permissions(manage_guild=True)
    async def set_(self, ctx):
        z = []
        for cmd in self.bot.get_command("set").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz ustawić:\n```\n{}```").format('\n'.join(z)))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def logs(self, ctx, channel: discord.TextChannel = None):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not option:
            await self.bot.pg_con.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", ctx.guild.id)

        if not channel:
            await ctx.send(_(ctx.lang, "Podaj kanał na którym będą wysyłane wszystkie logi."))

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))

            if msg.content.lower() == 'none':
                channel = None
            else:
                channel = await commands.TextChannelConverter().convert(ctx, msg.content.lower())
                if not channel:
                    return await ctx.send(_(ctx.lang, "Nie znaleziono tego kanału."))

        await self.bot.pg_con.execute("UPDATE guild_settings SET logs = $1 WHERE guild_id = $2",
                                      channel.id, ctx.guild.id)

        await self.update_cache(ctx.guild)

        return await ctx.send(":ok_hand:")

    @set_.command()
    @check_permissions(manage_guild=True)
    async def streams(self, ctx, channel: discord.TextChannel = None):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not option:
            await self.bot.pg_con.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", ctx.guild.id)

        if not channel:
            await ctx.send(_(ctx.lang,
                             "Podaj kanał na którym będą wysyłane wszystkie powiadomienia o transmisjach na żywo."))

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg = await self.bot.wait_for('message', check=check, timeout=60)
            except asyncio.TimeoutError:
                return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))

            if msg.content.lower() == 'none':
                channel = None
            else:
                channel = await commands.TextChannelConverter().convert(ctx, msg.content.lower())
                if not channel:
                    return await ctx.send(_(ctx.lang, "Nie znaleziono tego kanału."))

        await self.bot.pg_con.execute("UPDATE guild_settings SET streams_notifications = $1 WHERE guild_id = $2",
                                      channel.id, ctx.guild.id)

        await self.update_cache(ctx.guild)

        return await ctx.send(":ok_hand:")

    @set_.command(aliases=['lang'])
    @check_permissions(manage_guild=True)
    @commands.cooldown(1, 15, BucketType.guild)
    async def language(self, ctx, language: str):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not option:
            await self.bot.pg_con.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", ctx.guild.id)

        langs = ["PL", "ENG"]
        if not language.upper() in langs:
            return await ctx.send(_(ctx.lang, "Nie ma takiego języka. Użyj {}").format(', '.join(langs)))

        await self.bot.pg_con.execute("UPDATE guild_settings SET lang = $1 WHERE guild_id = $2",
                                      language.upper(), ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @set_.command()
    @check_permissions(manage_guild=True)
    async def warns_kick(self, ctx, number: int = None):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1",
                                             ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET warns_kick = $1 WHERE guild_id = $2",
                                      number, ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @set_.group(invoke_without_command=True)
    @check_permissions(manage_guild=True)
    async def blocked_commands(self, ctx):
        z = []
        for cmd in self.bot.get_command("set blocked_commands").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz ustawić:\n```\n{}```").format('\n'.join(z)))

    @blocked_commands.command(name="show", aliases=['list'])
    @check_permissions(manage_guild=True)
    async def show__(self, ctx):
        blocked_commands = await self.bot.pg_con.fetchval(
            "SELECT blocked_commands FROM guild_settings WHERE guild_id = $1",
            ctx.guild.id)
        if len(blocked_commands) == 0:
            return await ctx.send(_(ctx.lang, "Nie ma żadnych zablokowanych komend."))
        return await ctx.send("```" + '\n'.join(blocked_commands) + "```")

    @blocked_commands.command(name="add")
    @check_permissions(manage_guild=True)
    async def add__(self, ctx, *, command):
        """Dodaje komende do listy zablokowanych."""
        all_commands = []
        for cmd in self.bot.walk_commands():
            all_commands.append(cmd.name)
        if not command in all_commands:
            return await ctx.send(_(ctx.lang, "Nie ma takiej komendy."))

        functional_commands = ['help', 'set', 'setup']
        for cmd in self.bot.get_command('set').commands:
            if cmd.name not in functional_commands:
                functional_commands.append(cmd.name)

        if command in functional_commands:
            return await ctx.send(
                random.choice(["O.o", "o.O"]))  # yes im sending this only when you are doing something silly

        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)

        if command in option[0]['blocked_commands']:
            return await ctx.send(_(ctx.lang, "Ta komenda jest już zablokowana."))

        option[0]['blocked_commands'].append(command.lower())
        await self.bot.pg_con.execute("UPDATE guild_settings SET blocked_commands = $1 WHERE guild_id = $2",
                                      option[0]['blocked_commands'], ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @blocked_commands.command(name="remove")
    @check_permissions(manage_guild=True)
    async def remove__(self, ctx, *, command):
        """Usuwa komende z listy zablokowanych."""
        all_commands = []
        for cmd in self.bot.walk_commands():
            all_commands.append(cmd.name)

        if command not in all_commands:
            return await ctx.send(_(ctx.lang, "Nie ma takiej komendy."))

        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)

        if command not in option[0]['blocked_commands']:
            return await ctx.send(_(ctx.lang, "Ta komenda nie jest zablokowana."))

        option[0]['blocked_commands'].remove(command.lower())
        await self.bot.pg_con.execute("UPDATE guild_settings SET blocked_commands = $1 WHERE guild_id = $2",
                                      option[0]['blocked_commands'], ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @set_.command(aliases=['auto_role'])
    @check_permissions(manage_guild=True)
    async def autorole(self, ctx, role: str):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)

        if role.lower() == 'none':
            role = None
        else:
            role = await commands.RoleConverter().convert(ctx, role)
            role = role.id
        await self.bot.pg_con.execute("UPDATE guild_settings SET auto_role = $1 WHERE guild_id = $2", role,
                                      ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        option = await settings.get_guild_settings(self, member.guild.id)
        if option is None:
            return
        role = member.guild.get_role(option['auto_role'])
        if role:
            try:
                await member.add_roles(role)
            except discord.Forbidden:
                raise commands.BotMissingPermissions(["kick_members"])

        welcomer = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", member.guild.id)
        if option['welcome_text'] is not None and option['welcomer_channel'] is not None:
            channel = member.guild.get_channel(
                option['welcomer_channel'])
            if not option['welcome_text']:
                return
            if channel in ['to_edit', None] and option['welcome_text']:
                channel = member.guild.system_channel
            text = option['welcome_text']
            if text == None:
                return
            text = settings.replace_with_args(text, member)
            msg = await channel.send(text)
            if option['invite_blocker']:
                match = invite_regex.match(member.name.lower())
                if match:
                    await msg.delete()

    @set_.group(invoke_without_command=True)
    @check_permissions(manage_guild=True)
    async def blacklist(self, ctx):
        await ctx.send("```\n- add\n- remove\n- show\n- message\n```")

    @blacklist.command()
    @check_permissions(manage_guild=True)
    async def show(self, ctx):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not option[0]['blacklist']:
            return await ctx.send(_(ctx.lang, "Nie ma żadnych wyrazów w blackliście."))
        return await ctx.send('```' + ", ".join(option[0]['blacklist']) + '```')

    @blacklist.command(aliases=['warn'])
    @check_permissions(manage_guild=True)
    async def message(self, ctx, *, text):
        guild = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not text and guild:
            return await ctx.send(f"```{guild[0]['blacklist_warn']}```")
        if not text:
            return await ctx.send("Podaj tekst.")
        await self.bot.pg_con.execute("UPDATE guild_settings SET blacklist_warn = $1 WHERE guild_id = $2", text,
                                      ctx.guild.id)
        await ctx.send(':ok_hand:')

    @blacklist.command()
    @check_permissions(manage_guild=True)
    async def add(self, ctx, *, word):
        if len([word]) >= 2:
            return await ctx.send(_(ctx.lang, "Do blacklisty możesz dodać tylko **wyrazy**, nie zdania."))
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if word in option[0]['blacklist']:
            return await ctx.send(_(ctx.lang, "W blackliście jest już taki wyraz."))

        option[0]['blacklist'].append(word.lower())
        await self.bot.pg_con.execute("UPDATE guild_settings SET blacklist = $1 WHERE guild_id = $2",
                                      option[0]['blacklist'], ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @blacklist.command()
    @check_permissions(manage_guild=True)
    async def remove(self, ctx, *, word):
        if len([word]) >= 2:
            return await ctx.send(_(ctx.lang, "W blackliście, są tylko **wyrazy**, nie zdania."))
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not word in option[0]['blacklist']:
            return await ctx.send(_(ctx.lang, "W blackliście nie ma takiego wyrazu."))

        option[0]['blacklist'].remove(word.lower())
        await self.bot.pg_con.execute("UPDATE guild_settings SET blacklist = $1 WHERE guild_id = $2",
                                      option[0]['blacklist'], ctx.guild.id)
        return await ctx.send(":ok_hand:")

    @set_.command()
    @check_permissions(manage_guild=True)
    async def stars_count(self, ctx, number=None):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if str(number).isdigit():
            await self.bot.pg_con.execute("UPDATE guild_settings SET stars_count = $1 WHERE guild_id = $2", int(number),
                                          ctx.guild.id)
            return await ctx.send(":ok_hand:")
        else:
            return await ctx.send(_(ctx.lang, "To nie jest prawidłowa liczba."))

    @set_.group(invoke_without_command=True)
    @check_permissions(manage_guild=True)
    async def global_emojis(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET global_emojis = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, 'Ustawiono `global_emojis` na `{}`.').format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def self_starring(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET self_starring = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, "Ustawiono `self_starring` na `{}`.").format(answer))

    # @set_.command()
    # @check_permissions(manage_guild=True)
    # async def levels(self, ctx, answer: TrueFalseConverter=None):
    #     if not answer:
    #         raise TrueFalseError()
    #     option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
    #     await self.bot.pg_con.execute("
    #     UPDATE guild_settings SET levels = $1 WHERE guild_id = $2", answer, ctx.guild.id)
    #     await ctx.send(_(ctx.lang, "Ustawiono `levels` na `{}`.").format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def invite_blocker(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET invite_blocker = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, "Ustawiono `invite_blocker` na `{}`.").format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def emoji_censor(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET emoji_censor = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, "Ustawiono `emoji_censor` na `{}`.").format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def anti_raid(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET anti_raid = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, "Ustawiono `anti_raid` na `{}`.").format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def anti_link(self, ctx, answer: TrueFalseConverter = None):
        if not answer:
            raise TrueFalseError()
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        await self.bot.pg_con.execute("UPDATE guild_settings SET anti_link = $1 WHERE guild_id = $2", answer,
                                      ctx.guild.id)
        await ctx.send(_(ctx.lang, "Ustawiono `anti_link` na `{}`.").format(answer))

    @set_.command()
    @check_permissions(manage_guild=True)
    async def welcomer_channel(self, ctx, *, channel: str = None):
        welcomer = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not channel and welcomer:
            return await ctx.send(ctx.guild.get_channel(welcomer[0]['welcomer_channel']).mention)
        if channel.lower() == 'none':
            chann = None
        else:
            channel = await commands.TextChannelConverter().convert(ctx, channel)
            chann = channel.id
        if not channel:
            chan = await ctx.guild.create_text_channel(name='welcomer')
            await self.bot.pg_con.execute("UPDATE guild_settings SET welcomer_channel = $1 WHERE guild_id = $2",
                                          chan.id, ctx.guild.id)
            await ctx.send(':ok_hand:')
        if channel and welcomer:
            await self.bot.pg_con.execute("UPDATE guild_settings SET welcomer_channel = $1 WHERE guild_id = $2", chann,
                                          ctx.guild.id)
            await ctx.send(':ok_hand:')

    @set_.command()
    @check_permissions(manage_guild=True)
    async def welcome_text(self, ctx, *, text=None):
        welcomer = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
        if not text and welcomer:
            return await ctx.send(f"```{welcomer[0]['welcome_text']}```")
        if not welcomer[0]['welcomer_channel']:
            return await ctx.send(_(ctx.lang, "Najpierw ustaw kanał do powitań."))
        if not text:
            raise commands.UserInputError()
        await self.bot.pg_con.execute("UPDATE guild_settings SET welcome_text = $1 WHERE guild_id = $2", str(text),
                                      ctx.guild.id)
        await ctx.send(':ok_hand:')

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        guildd = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", guild.id)
        guild_prefixes = await self.bot.pg_con.fetch("SELECT * FROM prefixes WHERE guild_id = $1", guild.id)
        if guildd:
            await self.bot.pg_con.execute("DELETE FROM guild_settings WHERE guild_id = $1", guild.id)
        if guild_prefixes:
            await self.bot.pg_con.execute("DELETE FROM prefixes WHERE guild_id = $1", guild.id)

    @commands.Cog.listener()
    async def on_guild_join(self, g):
        guild = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", g.id)
        await self.bot.pg_con.execute("INSERT INTO guild_settings (guild_id) VALUES ($1)", g.id)
        for channel in g.text_channels:
            try:
                await channel.send(_(await get_language(self.bot, g.id),
                                     "Cześć, jestem {}. Dziękuje za dodanie mnie.\n\nJeśli będziesz potrzebował pomocy,"
                                     " dołącz - `/support`!\nAby wyświetlić pełną liste komend - `/help`.").format(
                    self.bot.user.name))
                break
            except discord.Forbidden:
                pass


class Mod(Plugin):
    def __init__(self, bot):
        self.bot = bot
        self.bansays_pl = ["**{}** został wysłany na wakacje.",
                           "Młotek sprawiedliwości uderzył tym razem w **{}**.",
                           "**{}** rozpłynął się w powietrzu."]
        self.bansays_en = ["**{}** was sent on holiday.",
                           "Justice hammer struck this time in **{}**.",
                           "**{}** melted in the air."]

    @commands.command(hidden=True)
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.send('Baj')
        await self.bot.logout()

    @commands.command(aliases=['b'])
    @check_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, member: typing.Union[discord.Member, discord.User], *,
                  reason: ModerationReason = None):
        if member.id == self.bot.user.id:
            await ctx.send(random.choice(["O.o", "o.O"]))
            return await add_react(ctx.message, False)
        if member.id == ctx.author.id:
            await ctx.send(_(ctx.lang, "Nie możesz zbanować sam siebie."))
            return await add_react(ctx.message, False)
        if member.top_role >= ctx.author.top_role:
            await ctx.send(_(ctx.lang, "Nie możesz zbanować osoby której najwyższa ranga jest nad twoją."))
            return await add_react(ctx.message, False)
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(_(ctx.lang, "Nie możesz zbanować osoby której najwyższa ranga jest nad moją."))
            return await add_react(ctx.message, False)
        lang = ctx.lang
        if lang == "PL":
            await ctx.send(random.choice(self.bansays_pl).format(member))
        if lang == "ENG":
            await ctx.send(random.choice(self.bansays_en).format(member))
        await member.ban(reason=reason)
        await member.send(_(ctx.lang, "Zostałeś zbanowany na `{}`.\nZa `{}`.").format(ctx.guild.name, reason))
        await add_react(ctx.message, True)
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command()
    @check_permissions(ban_members=True)
    async def unban(self, ctx, member: BannedMember, *, reason: ModerationReason = None):
        await ctx.guild.unban(member.user, reason=reason)
        if member.reason:
            await ctx.send(_(ctx.lang, "Odbanowano {}, który poprzednio został zbanowany za {}.").format(member.user, member.reason))
        else:
            await ctx.send(_(ctx.lang, "Odbanowano {}.").format(member.user))
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command(aliases=['k'])
    @commands.bot_has_permissions(kick_members=True)
    @check_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member = None, *, reason: ModerationReason = "Brak powodu"):
        """Wyrzuca osobe z serwera."""
        if member.id == self.bot.user.id:
            await ctx.send(random.choice(["O.o", "o.O"]))
            return await add_react(ctx.message, False)
        if member.id == ctx.author.id:
            await ctx.send(_(ctx.lang, "Nie możesz wyrzucić sam siebie."))
            return await add_react(ctx.message, False)
        if member.top_role >= ctx.author.top_role:
            await ctx.send(_(ctx.lang, "Nie możesz wyrzucić osoby której najwyższa ranga jest nad twoją."))
            return await add_react(ctx.message, False)
        if member.top_role >= ctx.guild.me.top_role:
            await ctx.send(_(ctx.lang, "Nie możesz wyrzucić osoby której najwyższa ranga jest nad moją."))
            return await add_react(ctx.message, False)
        lang = ctx.lang
        if lang == "PL":
            await ctx.send(random.choice(self.bansays_pl).format(member))
        if lang == "ENG":
            await ctx.send(random.choice(self.bansays_en).format(member))
        await member.kick(reason=reason)
        await member.send(_(ctx.lang, "Zostałeś wyrzucony z `{}`.\nZa `{}`.").format(ctx.guild.name, reason))
        await add_react(ctx.message, True)
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command()
    @commands.bot_has_permissions(kick_members=True)
    @check_permissions(kick_members=True)
    async def mute(self, ctx, member: discord.Member = None, *, time: EasyOneDayTime = None):
        """Wycisza osobe na zawsze, badź dany czas."""
        if member.id == self.bot.user.id:
            await ctx.send(random.choice(["O.o", "o.O"]))
            return await add_react(ctx.message, False)
        if member.id == ctx.author.id:
            await ctx.send(_(ctx.lang, "Nie możesz wyciszyć samego siebie."))
            return await add_react(ctx.message, False)
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if not role:
            role = await ctx.guild.create_role(name="Muted")
        await member.add_roles(role)
        await ctx.send(_(ctx.lang, "Drodzy państwo {} został wyciszony, wszyscy świętują.").format(member.mention))
        return await add_react(ctx.message, True)
        if time:
            await asyncio.sleep(time)
            if any(r.name == 'Muted' for r in ctx.author.roles):
                await member.remove_roles(role)
                return await ctx.send(_(ctx.lang, "{} został odciszony.").format(member.mention))
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command()
    @commands.bot_has_permissions(kick_members=True)
    @check_permissions(kick_members=True)
    async def unmute(self, ctx, member: discord.Member = None):
        """Odcisza wyciszoną osobe."""
        if member.id == self.bot.user.id:
            await ctx.send(random.choice(["O.o", "o.O"]))
            return await add_react(ctx.message, False)
        role = discord.utils.get(ctx.guild.roles, name="Muted")
        if any(r.name == 'Muted' for r in ctx.author.roles):
            await member.remove_roles(role)
            await ctx.send(_(ctx.lang, "{} został odciszony przez {}.").format(member.mention, ctx.author.mention))
            return await add_react(ctx.message, True)
        else:
            await ctx.send(_(ctx.lang, "**{}** nie jest wyciszony.").format(member))
            return await add_react(ctx.message, False)
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command(name="clear", aliases=["purge"])
    @commands.bot_has_permissions(manage_messages=True)
    @check_permissions(manage_messages=True)
    async def clear_(self, ctx, member: typing.Optional[discord.Member] = None, liczba=None):
        """Usuwa daną ilość wiadomości."""
        if liczba is None:
            raise commands.UserInputError()

        if liczba == "all":
            liczba = None
        else:
            try:
                liczba = int(liczba) + 1
            except ValueError:
                raise commands.UserInputError()

        if member is not None:
            def check(m):
                return m.author == member

            await ctx.channel.purge(limit=liczba, check=check)
        else:
            await ctx.channel.purge(limit=liczba)
        await ctx.send(_(ctx.lang, "Wyczyszczono **{}** wiadomości z {}.").format(
            liczba - 1 if liczba is not None else _(ctx.lang, "wszystkie"), ctx.channel.mention), delete_after=10)

        self.bot.dispatch('mod_command_use', ctx)

    async def get_warns(self, user_id, guild_id, ite=False):
        warns = await self.bot.pg_con.fetch(
            "SELECT * FROM warns WHERE user_id = $1 AND guild_id = $2 ORDER BY warn_num ASC", user_id, guild_id)
        if ite:
            if warns:
                return warns
        if warns:
            return warns[0]
        return None

    async def warns_num(self, user_id, guild_id, char="+"):
        warns = await self.bot.pg_con.fetch("SELECT * FROM warns WHERE user_id = $1 AND guild_id = $2", user_id,
                                            guild_id)
        if not warns:
            return 1
        if char == "+":
            return len(warns) + 1
        elif char == "-":
            return len(warns) - 1
        elif char == "/":
            return len(warns)

    async def remove_warn(self, user_id, guild_id, num):
        await self.bot.pg_con.execute("DELETE FROM warns WHERE user_id = $1 AND guild_id = $2 AND warn_num = $3",
                                      user_id, guild_id, num)

    async def clear_warns(self, user_id, guild_id):
        await self.bot.pg_con.execute("DELETE FROM warns WHERE user_id = $1 AND guild_id = $2", user_id, guild_id)

    async def check(self, user_id, guild_id):
        guild = await settings.get_guild_settings(self, guild_id)
        if await self.warns_num(user_id, guild_id, char="/") >= guild['warns_kick']:
            return True
        return False

    async def add_first_warn(self, user_id, guild_id, responsible_moderator_id, reason):
        warn_num = 1
        await self.bot.pg_con.execute(
            "INSERT INTO warns (user_id, guild_id, warn_num, reason, moderator) VALUES ($1, $2, $3, $4, $5)", user_id,
            guild_id, warn_num, reason, responsible_moderator_id)

    async def ask_for_action(self, ctx, member):
        msg = await ctx.send(
            _(ctx.lang, "{} ma już maksymalną ilość ostrzeżeń.\nPowinno się wyrzucić użykownika?").format(
                member.mention))
        await add_react(msg, True)
        await add_react(msg, False)

        def check(r, u):
            return u == ctx.author

        try:
            r, u = await self.bot.wait_for('reaction_add', check=check)
        except asyncio.TimeoutError:
            return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))

        if str(r.emoji) == '<:checkmark:601123463859535885>':
            await msg.edit(content=_(ctx.lang, "{} został wyrzucony.").format(str(member)))
            return True
        elif str(r.emoji) == '<:wrongmark:601124568387551232>':
            await msg.edit(content=_(ctx.lang, "{} nie został wyrzucony.").format(str(member)))
            return False
        else:
            await msg.edit(content=_(ctx.lang, "To nie jest prawidłowa reakcja."))
            return False

    async def add_warn(self, db, responsible_moderator_id, reason, ctx):
        warn_num = await self.warns_num(db['user_id'], db['guild_id'])
        await self.bot.pg_con.execute(
            "INSERT INTO warns (user_id, guild_id, warn_num, reason, moderator) VALUES ($1, $2, $3, $4, $5)",
            db['user_id'], db['guild_id'], warn_num, reason, responsible_moderator_id)
        if await self.check(db['user_id'], db['guild_id']):
            member = self.bot.get_guild(
                db['guild_id']).get_member(db['user_id'])
            ask = await self.ask_for_action(ctx, member)
            if ask:
                return await member.kick(reason=reason)

    @commands.group(invoke_without_command=True, aliases=['w'])
    @check_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member = None, *, reason: ModerationReason = 'Brak powodu'):
        """Daje ostrzeżenie."""
        if ctx.lang == "ENG" and reason == "Brak powodu":
            reason = "No reason"
        await ctx.invoke(self.bot.get_command("warn add"), member=member, reason=reason)

    @warn.command()
    @check_permissions(kick_members=True)
    async def add(self, ctx, member: discord.Member = None, *, reason: ModerationReason = 'Brak powodu'):
        """Daje ostrzeżenie."""
        if ctx.lang == "ENG" and reason == "Brak powodu":
            reason = "No reason"
        if member.id == self.bot.user.id:
            return await ctx.send(random.choice(["O.o", "o.O"]))
        if member.guild_permissions.administrator:
            return await ctx.send(_(ctx.lang, "Nie możesz dać ostrzeżenia administratorowi."))
        m = await self.get_warns(member.id, ctx.guild.id)
        if not m:
            await self.add_first_warn(member.id, ctx.guild.id, ctx.author.id, reason)
        else:
            await self.add_warn(m, ctx.author.id, reason, ctx)
        await ctx.send(_(ctx.lang, "{}, dostał ostrzeżenie za `{}`.").format(member.mention, reason))

    @warn.command()
    @check_permissions(kick_members=True)
    async def remove(self, ctx, member: discord.Member = None, number: int = None):
        """Usuwa ostrzeżenie po id."""
        if member.id == self.bot.user.id:
            return await ctx.send(random.choice(["O.o", "o.O"]))
        m = await self.get_warns(member.id, ctx.guild.id)
        if not m:
            return await ctx.send(_(ctx.lang, "{} nie posiada żadnych warnów.").format(member))
        await self.remove_warn(ctx.author.id, ctx.guild.id, number)
        return await ctx.send(_(ctx.lang, "{} usunął ostrzeżenie {}.").format(ctx.author.mention, member.mention))

    @warn.command(aliases=['purge'])
    @check_permissions(kick_members=True)
    async def clear(self, ctx, member: discord.Member = None):
        """Usuwa wszystkie ostrzeżenia."""
        if member.id == self.bot.user.id:
            return await ctx.send(random.choice(["O.o", "o.O"]))
        m = await self.get_warns(member.id, ctx.guild.id)
        if not m:
            return await ctx.send(_(ctx.lang, "{} nie posiada żadnych warnów.").format(member))
        await self.clear_warns(member.id, ctx.guild.id)
        return await ctx.send(_(ctx.lang, "{} wyczyscił ostrzeżenia {}.").format(ctx.author.mention, member.mention))

    @commands.command()
    @check_permissions(kick_members=True)
    async def warns(self, ctx, member: typing.Union[discord.User, discord.Member] = None):
        """Pokazuje wszystkie ostrzeżenia."""
        member = member or ctx.author
        warns = await self.get_warns(member.id, ctx.guild.id, True)
        if not warns:
            return await ctx.send(_(ctx.lang, "{}, nie ma żadnych warnów.").format(member))
        z = []
        i = 0
        lang = ctx.lang
        if lang == "PL":
            cor = "przez"
        elif lang == "ENG":
            cor = "by"

        z.append(f"{member}\n\n")

        for warn in warns:
            z.append("#{}  `{}` {} {}".format(
                warn['warn_num'], warn['reason'], cor, warn['moderator']))

        p = commands.Paginator()

        for line in z:
            p.add_line(line)
        for page in p.pages:
            await ctx.send(page)

def setup(bot):
    bot.add_cog(Settings(bot))
    bot.add_cog(Mod(bot))
    bot.add_cog(Plugins(bot))
