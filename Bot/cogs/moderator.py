import asyncio
import random
import re
import shlex
import json

import discord
import typing
from discord.ext import commands, tasks

from datetime import datetime, timedelta

from .classes import other
from .utils import fuzzy
from .classes.other import Plugin, Arguments
from .classes.converters import ModerationReason, VexsTimeConverter, EmojiConverter, ValueRangeFromTo, EmojiURL

from enum import Enum

EMOJI_REGEX = re.compile(r'<a?:.+?:([0-9]{15,21})>')
EMOJI_NAME_REGEX = re.compile(r'[0-9a-zA-Z\_]{2,32}')


def emoji_name(argument, *, regex=EMOJI_NAME_REGEX):
    m = regex.match(argument)
    if m is None:
        raise commands.BadArgument('Invalid emoji name.')
    return argument


class RaidEnum(Enum):
    off      = 0
    basic    = 1
    medium   = 2
    advanced = 3


class PunishmentEnum(Enum):
    none  = 0
    kick  = 1
    ban   = 2


# class AntiSpam:
#     def __init__(self, bot, context):
#         """
#         Basic representation for AntiSpam object, launch method is called when server decided to turn on antispam,
#         usually it's called with class:Raid.mode = 2
#
#         :param bot:
#         :param context:
#         """
#         self.bot = bot
#         self.ctx = context
#
#         self.guild_settings = bot._settings_cache.get(context.guild.id, bot.db.loop.create_task(self.get_settings))
#
#         self._message_cache = dict()  # i could use object from collections but let's keep it simple
#
#     async def get_settings(self):
#         guild = self.bot.get_guild_settings(self.ctx.guild.id)
#         return guild
#
#     @commands.Cog.listener()
#     async def on_message(self, message):
#         # dict = {id: {[message, message]}}
#
#         guild_ = self.guild_settings[message.guild.id]
#
#         if guild_.security['anti']['spam'] is False:
#             return
#
#         # if message.author.guild.guild_permissions.administrator:
#         #     return
#
#         if message.author.id in self._message_cache:
#             last = self._message_cache[message.author.id][-1]  # last component of list
#
#             if last.content != message.content and datetime.utcnow() - last.created_at >= timedelta(minutes=1):
#                 del self._message_cache[message.author.id]
#
#             else:
#                 self._message_cache[message.author.id].append(message)
#
#                 if len(self._message_cache[message.author.id]) >= guild_.security['spam_messages']:
#
#                     mod = self.bot.get_cog('moderator')
#                     if not mod:
#                         return commands.ExtensionNotLoaded
#
#                     self.ctx.author = self.bot.user
#                     await self.ctx.invoke(self.bot.get_command('warn'), member=message.author)
#
#         else:
#             self._message_cache[message.author.id] = [message]


class Moderator(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

        self.temps_checker.start()

    def cog_unload(self):
        self.temps_checker.cancel()

    @tasks.loop(seconds=5)
    async def temps_checker(self):
        temps = await self.bot.db.fetch("SELECT * FROM temps WHERE ends_at < $1 AND type = $2", datetime.utcnow(), 'temp_mute')

        for user in temps:
            guild_settings = await self.bot.get_guild_settings(user['guild_id'])

            lang = self.bot.get_language_object(guild_settings.language)
            moderator = self.bot.get_user(user['moderator_id'])

            guild = self.bot.get_guild(user['guild_id'])
            member = guild.get_member(user['user_id'])

            try:
                role = guild_settings.get_mute_role()
                if role:
                    try:
                        await member.remove_roles(role)
                        await self.bot.db.execute("DELETE FROM temps WHERE user_id = $1 AND guild_id = $2 AND type = $3", member.id, guild.id, 'temp_mute')
                    except discord.HTTPException:
                        pass
                    try:
                        await member.send(lang['unmute'].format(guild.name, user['reason'], moderator.mention))
                    except discord.HTTPException:
                        pass
            except discord.HTTPException:
                print("exc")
                # if moderator:
                #     await moderator.send(lang['could_not_unmute'])

    @temps_checker.before_loop
    async def before_temps(self):
        await self.bot.wait_until_ready()

    @commands.command(aliases=['emoji_created', 'emoji_add'])
    @commands.has_permissions(manage_emojis=True)
    async def add_emoji(self, ctx, name: emoji_name, *, emoji: EmojiURL):
        reason = await ModerationReason().convert(ctx, "Added Emoji")

        emoji_count = sum(e.animated == emoji.animated for e in ctx.guild.emojis)
        if emoji_count >= ctx.guild.emoji_limit:
            return await ctx.send(ctx.lang['max_emoji_slots'])

        async with self.bot.session.get(emoji.url) as resp:
            if resp.status >= 400:
                return await ctx.send(ctx.lang['could_not_fetch_image'])
            if int(resp.headers['Content-Length']) >= (256 * 1024):
                return await ctx.send(ctx.lang['too_big_image'])
            data = await resp.read()
            coro = ctx.guild.create_custom_emoji(name=name, image=data, reason=reason)
            async with ctx.typing():
                try:
                    created = await asyncio.wait_for(coro, timeout=10.0)
                except asyncio.TimeoutError:
                    return await ctx.send(ctx.lang['TimeoutError'])
                except discord.HTTPException as e:
                    return await ctx.send(ctx.lang['failed_to_add_emoji'].format(e))
                else:
                    return await ctx.send(ctx.lang['added_emoji'].format(created))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content):

        could_not_kick = list()
        kicked = list()

        for member in members:
            if member.id == self.bot.user.id:
                # await ctx.send(random.choice(["O.o", "o.O"]))
                if member not in could_not_kick:
                    could_not_kick.append(member)

            if member.id == ctx.author.id:
                # await ctx.send(ctx.lang['cant_kick_yourself'])
                if member not in could_not_kick:
                    could_not_kick.append(member)

            if member.top_role >= ctx.guild.me.top_role:
                # await ctx.send(ctx.lang['cant_kick_higher_than_bot'])
                if member not in could_not_kick:
                    could_not_kick.append(member)

            try:
                try:
                    await member.send(ctx.lang['you_been_kicked'].format(ctx.guild.name, reason))
                except discord.HTTPException:
                    pass

                await member.kick(reason=await ModerationReason().convert(ctx, reason))
                if member not in kicked and member not in could_not_kick:
                    kicked.append(member)
            except discord.HTTPException:
                if member not in could_not_kick:
                    could_not_kick.append(member)

        msg = f"{ctx.lang['kicked_member']}: {', '.join([f'{member.mention} ({member})' for member in kicked])} {ctx.lang['for']} `{reason}`."

        if len(could_not_kick) > 0:
            msg += f"\n{ctx.lang['could_not_kick']}: {', '.join([f'{member.mention} ({member})' for member in could_not_kick])}"
        await ctx.send(msg)
        self.bot.dispatch('mod_command_use', ctx)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], purge_days: typing.Optional[int] = 0, *, reason: commands.clean_content):

        could_not_ban = list()
        banned = list()

        for member in members:
            if member.id == self.bot.user.id:
                # await ctx.send(random.choice(["O.o", "o.O"]))
                if member not in could_not_ban:
                    could_not_ban.append(member)

            if member.id == ctx.author.id:
                # await ctx.send(ctx.lang['cant_ban_yourself'])
                if member not in could_not_ban:
                    could_not_ban.append(member)

            if member.top_role >= ctx.guild.me.top_role:
                # await ctx.send(ctx.lang['cant_ban_higher_than_bot'])
                if member not in could_not_ban:
                    could_not_ban.append(member)

            try:
                try:
                    await member.send(ctx.lang['you_been_kicked'].format(ctx.guild.name, reason))
                except discord.HTTPException:
                    pass

                await member.ban(reason=await ModerationReason().convert(ctx, reason), delete_message_days=purge_days)
                if member not in banned and member not in could_not_ban:
                    banned.append(member)
            except discord.HTTPException:
                if member not in could_not_ban:
                    could_not_ban.append(member)

        msg = ""

        if len(banned) > 0:
            msg += f"{ctx.lang['banned_member']}: {', '.join([f'{member.mention} ({member})' for member in banned])} {ctx.lang['for']} `{reason}` {ctx.lang['purged_msgs_ban'].format(purge_days)}."

        if len(could_not_ban) > 0:
            could_not_ban_msg = f"\n{ctx.lang['could_not_ban']}: {', '.join([f'{member.mention} ({member})' for member in could_not_ban])}"
            msg += could_not_ban_msg
        await ctx.send(msg)

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send(ctx.lang['too_many_messages'].format(limit))

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
        await ctx.message.delete()

        # spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        # messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        # if deleted:
        #     messages.append('')
        #     spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
        #     messages.extend(f'**{name}**: {count}' for name, count in spammers)
        #
        # to_send = '\n'.join(messages)

        # if len(to_send) > 2000:
        await ctx.send(ctx.lang['removed_messages'].format(deleted), delete_after=10)
        # else:
        #     await ctx.send(to_send, delete_after=10)

    @commands.group(aliases=["purge", "remove"], invoke_without_command=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, search: int):
        """Usuwa daną ilość wiadomości."""
        # channel = channel or ctx.channel
        # if liczba == "all":
        #     liczba = None
        # else:
        #     try:
        #         liczba = int(liczba) + 1
        #     except ValueError:
        #         raise commands.UserInputError()
        #
        # if member is not None:
        #     def check(m):
        #         return m.author == member
        #
        #     await channel.purge(limit=liczba, check=check)
        # else:
        #     await channel.purge(limit=liczba)
        # await ctx.send(ctx.lang['purged_message'].format(liczba - 1 if liczba is not None else ctx.lang['all_1'],
        #                                                  channel.mention), delete_after=10)

        await ctx.invoke(self._remove_all, search=search)

    @clear.command()
    async def embeds(self, ctx, search: int):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))
        self.bot.dispatch('mod_command_use', ctx)

    @clear.command()
    async def files(self, ctx, search: int):
        """Removes messages that have attachments in them."""
        await self.do_removal(ctx, search, lambda e: len(e.attachments))
        self.bot.dispatch('mod_command_use', ctx)

    @clear.command()
    async def images(self, ctx, search: int):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))
        self.bot.dispatch('mod_command_use', ctx)

    @clear.command(name='all')
    async def _remove_all(self, ctx, search: int):
        """Removes all messages."""
        await self.do_removal(ctx, search, lambda e: True)
        self.bot.dispatch('mod_command_use', ctx)

    @clear.command()
    async def user(self, ctx, member: discord.Member, search=100):
        """Removes all messages by the member."""
        await self.do_removal(ctx, search, lambda e: e.author == member)
        self.bot.dispatch('mod_command_use', ctx)

    @clear.command()
    async def contains(self, ctx, search: int, *, substr: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send(ctx.lang['clear_contains_more_than_3'])
        else:
            await self.do_removal(ctx, search, lambda e: substr in e.content)
            self.bot.dispatch('mod_command_use', ctx)

    @clear.command(name='bot')
    async def _bot(self, ctx, search: int, prefix=None):
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)

    @clear.command(name='emoji', aliases=['emojis'])
    async def _emoji(self, ctx, search: int):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r'<a?:[a-zA-Z0-9\_]+:([0-9]+)>')

        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @clear.command(name='reactions')
    async def _reactions(self, ctx, search: int):
        """Removes all reactions from messages that have them."""

        if search > 2000:
            return await ctx.send(ctx.lang['too_many_messages'].format(search))

        total_reactions = 0
        async for message in ctx.history(limit=search, before=ctx.message):
            if len(message.reactions):
                total_reactions += sum(r.count for r in message.reactions)
                await message.clear_reactions()

        await ctx.send(ctx.lang['removed_reactions'].format(total_reactions))

    @clear.command()
    async def custom(self, ctx, *, args: str):
        """A more advanced purge command.
        This command uses a powerful "command line" syntax.
        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.
        The messages are only deleted if all options are met unless
        the `--or` flag is passed, in which case only if any is met.
        The following options are valid.
        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: How many messages to search. Default 100. Max 2000.
        `--after`: Messages must come after this message ID.
        `--before`: Messages must come before this message ID.
        Flag options (no arguments):
        `--bot`: Check if it's a bot user.
        `--embeds`: Check if the message has embeds.
        `--files`: Check if the message has attachments.
        `--emoji`: Check if the message has custom emoji.
        `--reactions`: Check if the message has reactions
        `--or`: Use logical OR for all options.
        `--not`: Use logical NOT for all options.
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument('--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument('--files', action='store_const', const=lambda m: len(m.attachments))
        parser.add_argument('--reactions', action='store_const', const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int, default=100)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r'<:(\w+):(\d+)>')
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = all if not args._or else any

        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.do_removal(ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def temp_mute(self, ctx, members: commands.Greedy[discord.Member], time: VexsTimeConverter, *, reason: str):

        could_not_mute = list()
        muted = list()

        g = await self.bot.get_guild_settings(ctx.guild.id)
        role = g.get_mute_role()

        if not role:
            role = await ctx.guild.create_role(name="Muted")
            await self.bot.db.execute("UPDATE guild_settings SET mute_role = $1 WHERE guild_id = $2", role.id,
                                      ctx.guild.id)
            for channel in ctx.guild.channels:
                if isinstance(channel, discord.CategoryChannel):
                    await channel.set_permissions(role, send_messages=False, add_reactions=False, speak=False)
                else:
                    synced = channel._overwrites == channel.category._overwrites if channel.category else False
                    if not synced:
                        await channel.set_permissions(role, send_messages=False, add_reactions=False, speak=False)

        time_ = datetime.utcnow() + timedelta(seconds=time)
        now = datetime.utcnow()  # if now then now not in 5 seconds

        for member in members:
            if member.id == self.bot.user.id:
                if member not in could_not_mute:
                    could_not_mute.append(member)

            if member.id == ctx.author.id:
                if member not in could_not_mute:
                    could_not_mute.append(member)

            if member.top_role >= ctx.guild.me.top_role:
                if member not in could_not_mute:
                    could_not_mute.append(member)

            try:
                try:
                    await member.add_roles(role, reason=await ModerationReason().convert(ctx, reason))
                except discord.HTTPException:
                    if member not in could_not_mute:
                        could_not_mute.append(member)

                if member not in muted and member not in could_not_mute:
                    muted.append(member)
            except discord.HTTPException:
                if member not in could_not_mute:
                    could_not_mute.append(member)

        for member in muted:
            query = "INSERT INTO temps (type, role_id, moderator_id, timestamp, user_id, reason, ends_at, guild_id) " \
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            await self.bot.db.execute(query, 'temp_mute', role.id, ctx.author.id, now,
                                      member.id, reason, time_, ctx.guild.id)

            try:
                await member.send(ctx.lang['you_been_muted'].format(ctx.guild.name, time, reason))
            except discord.HTTPException:
                pass

        msg = f"{ctx.lang['muted_member']}: {', '.join([f'{member.mention} ({member})' for member in muted])} {ctx.lang['for']} `{reason}`."

        if len(could_not_mute) > 0:
            msg += f"\n{ctx.lang['could_not_mute']}: {', '.join([f'{member.mention} ({member})' for member in could_not_mute])}"
        await ctx.send(msg)

        self.bot.dispatch('mod_command_use', ctx)


    # warns

    @staticmethod
    async def punish(ctx, punishment, member, reason):
        if punishment == 0:  # just to be sure
            return
        elif punishment == 1:
            try:
                await member.kick(reason=await ModerationReason().convert(ctx, reason))
            except discord.HTTPException:
                return
        elif punishment == 2:
            try:
                await member.ban(reason=await ModerationReason().convert(ctx, reason))
            except discord.HTTPException:
                return
        else:
            return

    async def check(self, ctx, member, reason, all_warns, punish_without_asking):
        """
        :param reason:
        :param ctx:
        :param member:
        :return:
        """
        guild = await self.bot.get_guild_settings(ctx.guild.id)
        if all_warns >= guild.security['max_warns'] and guild.security['punishment'] > 0:
            if punish_without_asking:
                confirmation = True
            else:
                punishment = guild.security[
                    'punishment']  # TODO this means that something is wrong but lets keep this for now

                for p in PunishmentEnum:
                    if p.value == guild.security['punishment']:
                        punishment = p.name

                confirmation = await ctx.confirm(ctx.lang['confirm_punishment'].format(member.mention, punishment), ctx.author)
            if confirmation:
                await self.punish(ctx, guild.security['punishment'], member, reason)
                return False
            else:
                await ctx.send(ctx.lang['abort'])
                return True
        return True

    async def _get_id(self, member):
        warns = await self.bot.db.fetch("SELECT * FROM warns WHERE user_id = $1 AND guild_id = $2",
                                        member.id, member.guild.id)

        id_ = len(warns) + 1
        return id_

    async def add_warn(self, ctx, member, reason, *, punish_without_asking=False, check=True):
        id_ = await self._get_id(member)

        if check:
            ch = await self.check(ctx, member, reason, id_, punish_without_asking)
        else:
            ch = True
        if ch is True:
            await self.bot.db.execute("INSERT INTO warns (user_id, guild_id, moderator, id, reason, timestamp) VALUES "
                                      "($1, $2, $3, $4, $5, $6)",
                                      member.id, ctx.guild.id, ctx.author.id, id_, reason, datetime.utcnow())
            return True
        else:
            return False

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason: commands.clean_content):
        if member.id == self.bot.user.id:
            return await ctx.send(random.choice(["O.o", "o.O"]))

        if member.guild_permissions.administrator:
            return await ctx.send(ctx.lang['cant_warn'])

        z = await self.add_warn(ctx, member, reason)
        if z:
            await ctx.send(ctx.lang['warned_member'].format(member.mention, member, reason))
        else:
            return await ctx.send(ctx.lang['cant_warn'])

    @warn.command(aliases=['+'])
    @commands.has_permissions(kick_members=True)
    async def add(self, ctx, member: discord.Member, *, reason: commands.clean_content):
        await ctx.invoke(self.warn, member, reason=reason)

    @warn.command()
    @commands.has_permissions(kick_members=True)
    async def list(self, ctx, member: discord.Member):

        warns = await self.bot.db.fetch("SELECT * FROM warns WHERE user_id = $1 AND guild_id = $2 ORDER BY id ASC",
                                        member.id, ctx.guild.id)
        if not warns:
            return await ctx.send(ctx.lang['no_warns'])

        z = []
        for warn in warns:
            z.append(f"#{warn['id']} - `{warn['reason']}` - moderator: {warn['moderator']}")

        x = '\n'.join(z)
        return await ctx.send(f"```\n{x}\n```")

    @warn.command(aliases=['-', 'delete'])
    @commands.has_permissions(kick_members=True)
    async def remove(self, ctx, member: discord.Member, warn_id: int):
        warn = await self.bot.db.fetchrow("SELECT * FROM warns WHERE user_id = $1 and guild_id = $2 and id = $3",
                                          member.id, ctx.guild.id, warn_id)
        if not warn:
            return await ctx.send(ctx.lang['no_warn_with_that_id'].format(member))

        confirmation = await ctx.confirm(ctx.lang['confirm_removing_warn'].format(member.mention, warn['reason']), ctx.author)
        if confirmation:
            query_1 = "DELETE FROM warns WHERE user_id = $1 AND guild_id = $2 AND id = $3"
            query_2 = "UPDATE warns SET id = id - 1 WHERE user_id = $1 AND guild_id = $2 AND id > $3"

            await self.bot.db.execute(query_1, member.id, ctx.guild.id, warn_id)
            await self.bot.db.execute(query_2, member.id, ctx.guild.id, warn_id)

            await ctx.send(ctx.lang['removed_warn'])
        else:
            await ctx.send(ctx.lang['abort'])

    @warn.command(name="clear", aliases=['purge'])
    @commands.has_permissions(kick_members=True)
    async def clear_(self, ctx, member: discord.Member):
        warns = await self.bot.db.fetch("SELECT * FROM warns WHERE user_id = $1 and guild_id = $2",
                                        member.id, member.guild.id)

        if not warns:
            return await ctx.send(ctx.lang['no_warns'])

        confirmation = await ctx.confirm(ctx.lang['confirm_purging_warn'].format(len(warns), member.mention), ctx.author)

        if confirmation:
            query_1 = "DELETE FROM warns WHERE user_id = $1 AND guild_id = $2"

            await self.bot.db.execute(query_1, member.id, ctx.guild.id)

            await ctx.send(ctx.lang['purged_warns'])
        else:
            await ctx.send(ctx.lang['abort'])

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warns(self, ctx, member: discord.Member):
        await ctx.invoke(self.list, member)


class TrueFalseConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.lower() in ['true', '1', 'yes']:
            return True
        elif argument.lower() in ['false', '0', 'no']:
            return False
        else:
            raise commands.BadArgument(ctx.lang['true_false_error'])


class Settings(Plugin):
    def __init__(self, bot):
        super().__init__(bot, command_attrs={'not_turnable': True})
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def settings(self, ctx):
        guild = await self.bot.get_guild_settings(ctx.guild.id)
        e = discord.Embed()
        for key, value in guild:
            if key == "stars":
                stars = json.loads(value)
                    
                z = ""
                for key, value in stars.items():
                    
                    if value == "color":
                        value = str(value).replace("0x", "#")
                    
                    try:
                        channel_value = ctx.guild.get_channel(value)
                        value = channel_value.mention
                    except:
                        pass
                    
                    z += f"**{key}**: {value}\n"
                
                e.add_field(name="stars", value=z, inline=False)
            
            elif key == "security":
                security = json.loads(value)
                
                z = ""
                for key, value in security.items():
                    try:
                        channel_value = ctx.guild.get_channel(value)
                        value = channel_value.mention
                    except:
                        pass
                    
                    if key == 'anti':
                        z += f"**anti**:\n```"
                        x = ""
                        for anti_key, anti_value in value.items():
                            x += f"{anti_key}: {anti_value}\n"
                        z += f"{x}```"
                    else:
                        z += f"{key}: `{value}`\n"
                
                e.add_field(name="security", value=z, inline=False)
            
            elif key == "stats":
                stats = json.loads(value)
                print(stats)
                
                z = ""
                for org_key, value in stats.items():
                    z += f"**{org_key}**:\n"
                    for key, value in value.items():
                        try:
                            channel_value = ctx.guild.get_channel(value)
                            value = channel_value.mention
                        except:
                            pass
                        
                        z += f"{key}: `{value}`\n"
                    
                e.add_field(name="stats", value=z, inline=False)
            
            else:
                try:
                    channel_value = ctx.guild.get_channel(value)
                    value = channel_value.mention
                except:
                    pass
                
                try:
                    role_value = ctx.guild.get_role(value)
                    value = role_value.mention
                except:
                    pass
                
                e.add_field(name=key, value=value, inline=False)
        await ctx.send(embed=e)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def plugin(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @plugin.command(aliases=['on'])
    @commands.has_permissions(manage_guild=True)
    async def enable(self, ctx, *, name):
        all_cogs_names = [cog.lower() for cog in self.bot.cogs]

        if name not in all_cogs_names:
            return await ctx.send(ctx.lang['plugin_doesnt_exist'])

        module = fuzzy.extract_one(name, self.bot.cogs)

        await module[2].turn_on(ctx.guild.id)

        await ctx.send(ctx.lang['turn_on_plugin'])

    @plugin.command(aliases=['off'])
    @commands.has_permissions(manage_guild=True)
    async def disable(self, ctx, *, name):
        all_cogs_names = [cog.lower() for cog in self.bot.cogs]

        if name not in all_cogs_names:
            return await ctx.send(ctx.lang['plugin_doesnt_exist'])

        module = fuzzy.extract_one(name, self.bot.cogs)

        await module[2].turn_off(ctx.guild.id)

        await ctx.send(ctx.lang['turn_off_plugin'])

    @commands.group(name="set", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def set_(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, *, prefix: commands.clean_content):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('prefix', prefix)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('prefix', prefix))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['delete', 'remove', 'none'])
    @commands.has_permissions(manage_guild=True)
    async def null(self, ctx, option: str):

        options = ['welcome_text', 'welcome_channel', 'logs', 'leave_text', 'leave_channel', 'auto_role',
                   'stream_notification',]

        if option not in options:
            return await ctx.send(ctx.lang['thing_is_not_settable'])

        guild = await self.bot.get_guild_settings(ctx.guild.id)
        s = await guild.set(option, None)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format(option, "None"))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['lockdown'])
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: typing.Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        try:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False)
            }
            await channel.edit(overwrites=overwrites)
            return await ctx.add_react(True)
        except Exception as e:
            await ctx.send(e)
            return await ctx.add_react(False)

    @set_.command(aliases=['cooldown'])
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, channel: typing.Optional[discord.TextChannel] = None, number: float = 3):
        channel = channel or ctx.channel
        try:
            await channel.edit(slowmode_delay=number)
            return await ctx.add_react(True)
        except Exception as e:
            await ctx.send(e)
            return await ctx.add_react(False)

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def levels(self, ctx, value: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stars('levels', value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('levels', value))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def leveling_type(self, ctx, value: ValueRangeFromTo(1, 3)):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        if not value:
            raise commands.BadArgument("Argument `value` has to be in range from 1 to 3, where 3 is the hardest and 1 is the easiest.")

        s = await guild.set_stars('leveling_type', value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leveling_type', value))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def anti_link(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('link', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_link', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def anti_invites(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('invites', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_invites', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def anti_spam(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('spam', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_spam', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def anti_caps(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('caps', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_caps', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(enabled=False)
    @commands.has_permissions(manage_guild=True)
    async def anti_nsfw(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('nsfw', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_nsfw', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def anti_images(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('images', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_images', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['raid_mode'])
    @commands.has_permissions(manage_guild=True)
    async def raid(self, ctx, mode: int):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        if mode > 3:
            return await ctx.send(ctx.lang['too_big_raid_mode'])

        for i in RaidEnum:
            if i.value == mode:
                mode = i

        s = await guild.set_security("raid_mode", mode.value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format("raid_mode", f"{mode.value} ({mode})"))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['punishement'])
    @commands.has_permissions(manage_guild=True)
    async def punishements(self, ctx, mode: int):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        if mode > 2:
            return await ctx.send(ctx.lang['too_big_punishemnt_mode'])

        for i in RaidEnum:
            if i.value == mode:
                mode = mode

        s = await guild.set_security("raid_mode", mode.value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format("raid_mode", f"{mode.value} ({mode})"))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def welcome_text(self, ctx, *, text: str):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('welcome_text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('welcome_text', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def welcome_channel(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('welcome_channel', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('welcome_channel', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def logs(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        url = f"https://cdn.discordapp.com/avatars/{self.bot.user.id}/{self.bot.user.avatar}.png"
        avatar = await other.get_avatar_bytes(url)
        webhook = await channel.create_webhook(name="Rose logging", avatar=avatar)

        old_webhook = await self.bot.cogs['Logs'].get_logs_webhook(guild['logs_webhook'])
        if old_webhook:
            await old_webhook.delete()

        s = await guild.set('logs', channel.id)
        ls = await guild.set('logs_webhook', webhook.id)
        if s and ls:
            return await ctx.send(ctx.lang['updated_setting'].format('logs', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['lang'])
    @commands.has_permissions(manage_guild=True)
    async def language(self, ctx, lang: str):
        if lang.lower() not in ["pl", "eng"]:
            return await ctx.send(ctx.lang['wrong_language'])

        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('lang', lang.upper())
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('language', lang.upper()))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def leave_text(self, ctx, *, text: str):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('leave_text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leave_text', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def leave_channel(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('leave_channel', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leave_channel', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def auto_role(self, ctx, role: discord.Role):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('auto_role', role.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leave_channel', '@' + str(role)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def starboard(self, ctx, channel: discord.TextChannel = None):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        starboard = guild.get_starboard()
        if starboard and not channel:
            ch = await ctx.confirm(ctx.lang['confirm_removing_starboard'], ctx.author)
            if ch:
                await starboard.delete(reason=ctx.lang['created_new_starboard'])

                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
                }

                channel = await ctx.guild.create_text_channel(name="starboard", overwrites=overwrites)
            else:
                return await ctx.send(ctx.lang['abort'])

        elif not channel:
            overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(send_messages=False, read_messages=True),
            }

            channel = await ctx.guild.create_text_channel(name="starboard", overwrites=overwrites)

        s = await guild.set_stars('starboard', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('starboard', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def stars_emoji(self, ctx, emoji: EmojiConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stars('emoji', emoji)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('stars_emoji', emoji))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def stars_color(self, ctx, color):

        hex_ = re.search(r'^#?(?:[0-9a-fA-F]{3}){1,2}$', color)

        if not hex_:
            return await ctx.send(ctx.lang['color_has_to_be_hex'])

        guild = await self.bot.get_guild_settings(ctx.guild.id)

        color = color.replace("#", "")

        s = await guild.set_stars('color', color)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('stars_color', color))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def self_starring(self, ctx, value: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stars('self_starring', value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('self_starring', value))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def stars_count(self, ctx, value: ValueRangeFromTo(1, 13)):  # 1 to 12
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        if not value:
            return await ctx.send(ctx.lang['stars_count_bad_range'])

        s = await guild.set_stars('stars_count', value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('stars_count', value))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    @commands.has_permissions(manage_guild=True)
    async def stream_notification(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('stream_notification', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('stream_notification', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def stats(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def new_member(self, ctx, channel: discord.VoiceChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('new_member', 'channel_id', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('new_member', "\U0001f508 " + channel.name))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def new_member_text(self, ctx, *, text: commands.clean_content()):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('new_member', 'text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('new_member_text', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def members(self, ctx, channel: discord.VoiceChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('members', 'channel_id', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('members', "\U0001f508 " + channel.name))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def members_text(self, ctx, *, text: commands.clean_content()):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('members', 'text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('members', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command(aliases=['online_top'])
    @commands.has_permissions(manage_guild=True)
    async def online_record(self, ctx, channel: discord.VoiceChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('online_top', 'channel_id', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('online_top', "\U0001f508 " + channel.name))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command(aliases=['online_top_text'])
    @commands.has_permissions(manage_guild=True)
    async def online_record_text(self, ctx, *, text: commands.clean_content()):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('online_top', 'text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('online_top', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def online_members(self, ctx, channel: discord.VoiceChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('online_members', 'channel_id', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('online_members', "\U0001f508 " + channel.name))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @stats.command()
    @commands.has_permissions(manage_guild=True)
    async def online_members_text(self, ctx, *, text: commands.clean_content()):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_stats('online_members', 'text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('online_members', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @commands.command(hidden=True, enabled=False)  # discord patched this char
    @commands.has_permissions(manage_channels=True)
    async def space(self, ctx, channel):
        if channel == "all":
            for channel in ctx.guild.channels:
                await channel.edit(name=channel.name.replace("-", " ").replace("_", " "))
        else:
            channel = await commands.TextChannelConverter().convert(ctx, channel)
            if not channel:
                channel = await commands.VoiceChannelConverter().convert(ctx, channel)
                if not channel:
                    return await ctx.send(ctx.lang[''])

            await channel.edit(name=channel.name.replace("-", " ").replace("_", " "))


def setup(bot):
    bot.add_cog(Settings(bot))
    bot.add_cog(Moderator(bot))
