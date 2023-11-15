import asyncio

import discord
from discord.ext import commands

from .classes.other import Plugin


DEFAULT_QUEUE_LIMIT = 2


class Stats(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        
        self.member_queue = dict()
        self.member_queue_update = DEFAULT_QUEUE_LIMIT
        
    @commands.Cog.listener()
    async def on_member_join(self, member):  # online members
        guild = await self.bot.get_guild_settings(member.guild.id)

        members = guild.stats['members']['channel_id']
        all_members = guild.stats['all_members']['channel_id']
        new_member = guild.stats['new_member']['channel_id']
        bots = guild.stats['bots']['channel_id']

        if not member.bot:
            if members:
                channel = member.guild.get_channel(members)
                try:

                    await channel.edit(name=guild.stats['members']['text'].format(
                        len([m for m in member.guild.members if not m.bot])))

                except (discord.Forbidden, discord.HTTPException):
                    pass

        if all_members:
            channel = member.guild.get_channel(all_members)
            try:
                await channel.edit(name=guild.stats['all_members']['text'].format(member.guild.member_count))
            except (discord.Forbidden, discord.HTTPException):
                pass

        if new_member:
            channel = member.guild.get_channel(new_member)
            try:
                await channel.edit(name=guild.stats['new_member']['text'].format(str(member)))
            except (discord.Forbidden, discord.HTTPException):
                pass

        if member.bot:
            if bots:
                channel = member.guild.get_channel(bots)
                try:

                    await channel.edit(name=guild.stats['bots']['text'].format(
                        len([m for m in member.guild.members if m.bot])))

                except (discord.Forbidden, discord.HTTPException):
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = await self.bot.get_guild_settings(member.guild.id)

        members = guild.stats['members']['channel_id']
        all_members = guild.stats['all_members']['channel_id']
        new_member = guild.stats['new_member']['channel_id']
        bots = guild.stats['bots']['channel_id']

        if not member.bot:
            if members:
                channel = member.guild.get_channel(members)
                try:

                    await channel.edit(name=guild.stats['members']['text'].format(
                        len([m for m in member.guild.members if not m.bot])))

                except (discord.Forbidden, discord.HTTPException):
                    pass

        if all_members:
            channel = member.guild.get_channel(all_members)
            try:
                await channel.edit(name=guild.stats['all_members']['text'].format(member.guild.member_count))
            except (discord.Forbidden, discord.HTTPException):
                pass

        if new_member:
            latest = lambda m: sorted(m, key=lambda tm: tm.joined_at)[-1]

            channel = member.guild.get_channel(new_member)
            try:
                await channel.edit(name=guild.stats['new_member']['text'].format(str(latest)))
            except (discord.Forbidden, discord.HTTPException):
                pass

        if member.bot:
            if bots:
                channel = member.guild.get_channel(bots)
                try:

                    await channel.edit(name=guild.stats['bots']['text'].format(
                        len([m for m in member.guild.members if m.bot])))

                except (discord.Forbidden, discord.HTTPException):
                    pass

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        guild = await self.bot.get_guild_settings(after.guild.id)

        online_record = guild.stats['online_top']['channel_id']
        online = [m for m in after.guild.members if m.status != discord.Status.offline]

        if online_members := guild.stats['online_members']['channel_id']:
            if self.member_queue_update == 0:
                try:
                    channel = self.bot.get_channel(online_members)
                    await channel.edit(name=guild.stats['online_members']['text'].format(len(online)))
                except (discord.Forbidden, discord.HTTPException):
                    pass
                self.member_queue_update = DEFAULT_QUEUE_LIMIT
            else:
                self.member_queue_update -= 1

        if guild.stats['online_top']['record'] < len(online):
            await guild.set_stats('online_top', 'record', len(online))

        if online_record:
            channel = after.guild.get_channel(online_record)

            try:
                await channel.edit(name=guild.stats['online_top']['text'].format(len(online)))
            except (discord.Forbidden, discord.HTTPException):
                pass


def setup(bot):
    bot.add_cog(Stats(bot))
