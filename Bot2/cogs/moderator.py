import random

import discord
import typing
from discord.ext import commands, tasks

from datetime import datetime, timedelta

from .classes.other import Plugin
from .classes.converters import ModerationReason, VexsTimeConverter

from .utils import clean_text

from enum import Enum


class RaidEnum(Enum):
    off      = 0
    basic    = 1
    medium   = 2
    advanced = 3


class PunishmentEnum(Enum):
    none  = 0
    kick  = 1
    ban   = 2


class AntiSpam:
    def __init__(self, bot, context):
        """
        Basic representation for AntiSpam object, launch method is called when server decided to turn on antispam,
        usually it's called with class:Raid.mode = 2

        :param bot:
        :param context:
        """
        self.bot = bot
        self.ctx = context

        self.guild_settings = bot._settings_cache.get(context.guild.id, bot.db.loop.create_task(self.get_settings))

        self._message_cache = dict()  # i could use object from collections but let's keep it simple

    async def get_settings(self):
        guild = self.bot.get_guild_settings(self.ctx.guild.id)
        return guild

    @commands.Cog.listener()
    async def on_message(self, message):
        # dict = {id: {[message, message]}}

        guild_ = self.guild_settings[message.guild.id]

        if guild_.security['anti']['spam'] is False:
            return

        if message.author.guild.guild_permissions.administrator:
            return

        if message.author.id in self._message_cache:
            last = self._message_cache[message.author.id][-1]  # last component of list

            if last.content != message.content and datetime.utcnow() - last.created_at >= timedelta(minutes=1):
                del self._message_cache[message.author.id]

            else:
                self._message_cache[message.author.id].append(message)

                if len(self._message_cache[message.author.id]) >= guild_.security['spam_messages']:

                    mod = self.bot.get_cog('moderator')
                    if not mod:
                        return commands.ExtensionNotLoaded

                    self.ctx.author = self.bot.user
                    await self.ctx.invoke(self.bot.get_command('warn'), member=message.author)

        else:
            self._message_cache[message.author.id] = [message]


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

            lang = self.bot.polish if guild_settings.language == "PL" else self.bot.english
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

    @commands.command(aliases=["purge"])
    @commands.bot_has_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, member: typing.Optional[discord.Member], channel: typing.Optional[discord.TextChannel],
                    liczba):
        """Usuwa daną ilość wiadomości."""
        channel = channel or ctx.channel
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

            await channel.purge(limit=liczba, check=check)
        else:
            await channel.purge(limit=liczba)
        await ctx.send(ctx.lang['purged_message'].format(liczba - 1 if liczba is not None else ctx.lang['all_1'],
                                                         channel.mention), delete_after=10)

        self.bot.dispatch('mod_command_use', ctx)

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

    async def add_warn(self, ctx, member, reason, *, punish_without_asking=False):
        id_ = await self._get_id(member)

        ch = await self.check(ctx, member, reason, id_, punish_without_asking)
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
        super().__init__(bot)
        self.bot = bot

    @commands.group(name="set", invoke_without_command=True)
    async def set_(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @set_.command()
    async def anti_link(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('link', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_link', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def anti_invites(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('invites', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_invites', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def anti_spam(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('spam', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_spam', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def anti_images(self, ctx, argument: TrueFalseConverter):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set_security('images', str(argument), base='anti')
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('anti_images', str(argument)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['raid_mode'])
    async def raid(self, ctx, mode: int):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        if mode > 3:
            return await ctx.send(ctx.lang['too_big_raid_mode'])

        for i in RaidEnum:
            if i.value == mode:
                mode = mode

        s = await guild.set_security("raid_mode", mode.value)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format("raid_mode", f"{mode.value} ({mode})"))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command(aliases=['punishement'])
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
    async def welcome_text(self, ctx, *, text: str):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('welcome_text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('welcome_text', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def welcome_channel(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('welcome_channel', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('welcome_channel', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def leave_text(self, ctx, *, text: str):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('leave_text', text)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leave_text', text))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def leave_channel(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('leave_channel', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('leave_channel', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))

    @set_.command()
    async def stream_notification(self, ctx, channel: discord.TextChannel):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        s = await guild.set('stream_notification', channel.id)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format('stream_notification', '#' + str(channel)))
        else:
            return await ctx.send(ctx.lang['something_happened'].format(ctx.prefix))


def setup(bot):
    bot.add_cog(Settings(bot))
    bot.add_cog(Moderator(bot))
