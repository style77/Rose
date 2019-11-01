import random

import discord
from discord.ext import commands, tasks

from datetime import datetime, timedelta

from .classes.other import Plugin
from .classes.converters import ModerationReason

from .utils import clean_text

from enum import Enum


class RaidEnum(Enum):
    off      = 0
    basic    = 1
    medium   = 2
    advanced = 3


class Raid:
    def __init__(self):
        self.mode = 0

    def to_json(self):
        return {'mode': self.mode}

    def update(self, mode: int):
        for v in RaidEnum:
            if v.value == mode:
                self.mode = v
                break


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

        if message.author.id in self._message_cache:
            last = self._message_cache[message.author.id][-1]  # last component of list

            if last.content != message.content and datetime.utcnow() - last.created_at >= timedelta(minutes=1):
                del self._message_cache[message.author.id]

            else:
                self._message_cache[message.author.id].append(message)

                if len(self._message_cache[message.author.id]) >= guild_.security['spam_messages']:

                    mod = self.bot.get_cog('Moderator')
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

    @tasks.loop()
    async def temps_checker(self):
        def get_temps():
            temps = self.bot.db.fetch("SELECT * FROM temps WHERE ends_at < $1", datetime.utcnow())
            return temps

        async for user in get_temps():
            guild_settings = self.bot._settings_cache.get(user['guild_id'], None)
            if not guild_settings:
                guild_settings = self.bot._settings_cache[user['guild_id']] = await self.bot.get_guild_settings(user['guild_id'])

            lang = self.bot.polish if guild_settings.language == "PL" else self.bot.english
            moderator = self.bot.get_user(user['moderator_id'])

            guild = self.bot.get_guild(user['guild_id'])
            member = guild.get_member(user['user_id'])

            try:
                role = guild_settings.get_mute_role()
                if role:
                    await member.remove_roles(role)
                    try:
                        await member.send(lang['unmute'].format(guild.name, user['reason'], moderator.mention))
                    except discord.HTTPException:
                        return
            except discord.HTTPException:
                if moderator:
                    await moderator.send(lang['could_not_unmute'])

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

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content):

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
                await member.ban(reason=await ModerationReason().convert(ctx, reason))
                if member not in banned and member not in could_not_ban:
                    banned.append(member)
            except discord.HTTPException:
                if member not in could_not_ban:
                    could_not_ban.append(member)

        msg = f"{ctx.lang['banned_member']}: {', '.join([f'{member.mention} ({member})' for member in banned])} {ctx.lang['for']} `{reason}`."

        if len(could_not_ban) > 0:
            msg += f"\n{ctx.lang['could_not_ban']}: {', '.join([f'{member.mention} ({member})' for member in could_not_ban])}"
        await ctx.send(msg)

    @commands.command()
    async def temp_mute(self):
        pass


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

        s = await guild.set(self.__name__, str(argument))
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format(self.__name__, str(argument)))

    @set_.command(aliases=['raid_mode'])
    async def raid(self, ctx, mode: int):
        guild = await self.bot.get_guild_settings(ctx.guild.id)

        for i in RaidEnum:
            if i.value == mode:
                mode = mode

        s = await guild.set("raid_mode", mode)
        if s:
            return await ctx.send(ctx.lang['updated_setting'].format("raid_mode", f"{mode.value} ({mode})"))


def setup(bot):
    bot.add_cog(Settings(bot))
    bot.add_cog(Moderator(bot))
