import aiohttp
import discord

import functools

from discord.ext import commands

from .classes import other
from .classes.other import Plugin
from .utils import get_language


class Logs(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def get_logs_webhook(self, webhook_id):
        if not webhook_id:
            return None

        try:
            webhook = await self.bot.fetch_webhook(webhook_id)
        except discord.NotFound:
            return None
        return webhook

    async def get_logs_channel(self, guild_id):
        guild = await self.bot.get_guild_settings(guild_id)
        if guild['logs']:
            logs_webhook = guild['logs_webhook']
            channel = await self.get_logs_webhook(logs_webhook)

            if not channel:
                channel = self.bot.get_channel(guild['logs'])

                url = f"https://cdn.discordapp.com/avatars/{self.bot.user.id}/{self.bot.user.avatar}.png"
                avatar = await other.get_avatar_bytes(url)

                logs_webhook = await channel.create_webhook(name="Rose logging", avatar=avatar)
                logs_webhook = logs_webhook.id
                await guild.set('logs_webhook', logs_webhook)

            channel = await self.get_logs_webhook(logs_webhook)
            if channel:
                return channel
        return None

    @commands.Cog.listener()
    async def on_message_delete(self, m):
        if m.author == self.bot.user:
            return

        if not m.guild:
            return

        ch = await self.get_logs_channel(m.guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(m.guild.id)
        lang = self.bot.get_language_object(guild.language)

        e = discord.Embed(description=lang['message_deleted'].format(
            m.author.mention, m.channel.mention, m.content),
            color=0xb8352c,
            timestamp=m.created_at)
        e.set_author(name=m.author, icon_url=m.author.avatar_url)

        if m.attachments:
            e.set_image(url=m.attachments[0].url)

        e.set_footer(text=f"ID: {m.author.id}")

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, m):
        if not m[0].guild:
            return

        ch = await self.get_logs_channel(m[0].guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(m[0].guild.id)
        lang = self.bot.get_language_object(guild.language)

        # content = []
        # for msg in m:
        #     if not msg.content:
        #         continue

        #     content.append(f"{msg.author}: {msg.content} //{str(msg.created_at)}\n")

        e = discord.Embed(description=lang['bulk_message_deleted'].format(len(m), m[0].channel.mention),
                          color=0x6e100a,
                          timestamp=m[0].created_at)
        e.set_author(name=m[0].guild, icon_url=m[0].guild.icon_url)


        func = functools.partial(self.bot.cogs['Useful'].processing, m)
        
        buf = await self.bot.loop.run_in_executor(None, func)
        
        f = discord.File(filename=f"{m[0].channel.name}.txt", fp=buf)

        await ch.send(embed=e)
        await ch.send(file=f)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild:
            return
        ch = await self.get_logs_channel(after.guild.id)
        if not ch:
            return

        if before.content == after.content:
            return
        if before.author.bot:
            return
        if not before.content or not after.content:
            return

        guild = await self.bot.get_guild_settings(after.guild.id)
        lang = self.bot.get_language_object(guild.language)

        e = discord.Embed(
            description=lang['message_edited'].format(after.channel.mention, after.jump_url),
            color=0xfabc11, timestamp=before.created_at)
        e.add_field(name=lang['before'], value=before.content, inline=False)
        e.add_field(name=lang['after'], value=after.content, inline=False)

        if before.attachments:
            e.set_image(url=before.attachments[0].url)
        if after.attachments:
            e.set_image(url=after.attachments[0].url)

        e.set_author(name=after.author, icon_url=after.author.avatar_url)
        e.set_footer(text="ID: {}".format(after.author.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_mod_command_use(self, ctx):
        if not ctx.guild:
            return

        ch = await self.get_logs_channel(ctx.guild.id)
        if not ch:
            return

        e = discord.Embed(description=ctx.lang['used_command'].format(ctx.author.mention, ctx.command.qualified_name),
                          color=discord.Color.blurple(),
                          timestamp=ctx.message.created_at)

        e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        e.set_footer(text="ID: {}".format(ctx.author.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_prefix_change(self, ctx, new_prefix):
        if not ctx.guild:
            return

        ch = await self.get_logs_channel(ctx.guild.id)
        if not ch:
            return

        e = discord.Embed(description=ctx.lang['changed_prefix'].format(ctx.author.mention, new_prefix),
                          color=discord.Color.blurple(),
                          timestamp=ctx.message.created_at)

        e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        e.set_footer(text="ID: {}".format(ctx.author.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        ch = await self.get_logs_channel(member.guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(member.guild.id)
        lang = self.bot.get_language_object(guild.language)

        e = discord.Embed(description=lang['member_joined'].format(member.mention, member, member.guild.name,
                                                                   str(member.created_at)),
                          color=discord.Color.green(),
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        ch = await self.get_logs_channel(member.guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(member.guild.id)
        lang = self.bot.get_language_object(guild.language)

        e = discord.Embed(description=lang['leaved_server'].format(member.mention, member, member.joined_at),
                          color=0x6e100a,
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = await self.get_logs_channel(guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(guild.id)
        lang = self.bot.get_language_object(guild.language)

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user:
                    moderator = entry.user
                    reason = entry.reason if entry.reason else lang['no_reason']

            try:
                text = lang['member_banned_with_reason'].format(user.mention, moderator.mention, reason)
            except UnboundLocalError:
                text = lang['member_banned'].format(user.mention)
        except discord.Forbidden:
            text = lang['member_banned'].format(user.mention)

        e = discord.Embed(description=text,
                          color=0x22488a,
                          timestamp=user.created_at)

        e.set_author(name=user, icon_url=user.avatar_url)
        e.set_footer(text="ID: {}".format(user.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        ch = await self.get_logs_channel(guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(guild.id)
        lang = self.bot.get_language_object(guild.language)

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user:
                    moderator = entry.user
                    reason = entry.reason if entry.reason else lang['no_reason']

            try:
                text = lang['member_unbanned_with_reason'].format(user, moderator.mention, reason)
            except UnboundLocalError:
                text = lang['member_unbanned'].format(user)
        except discord.Forbidden:
            text = lang['member_unbanned'].format(user)

        e = discord.Embed(description=text,
                          color=0x22488a,
                          timestamp=user.created_at)

        e.set_author(name=user, icon_url=user.avatar_url)
        e.set_footer(text="ID: {}".format(user.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_update(self, before, update):  # todo
        pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        ch = await self.get_logs_channel(role.guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(role.guild.id)
        lang = self.bot.get_language_object(guild.language)

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create):
                if entry.target == role:
                    moderator = entry.user

            try:
                text = lang['role_created_by'].format(role.mention, moderator.mention)
            except UnboundLocalError:
                text = lang['role_created'].format(role.mention)
        except discord.Forbidden:
            text = lang['role_created'].format(role.mention)

        e = discord.Embed(description=text,
                          color=0xe69645,
                          timestamp=role.created_at)

        e.set_author(name=role.guild, icon_url=role.guild.icon_url)
        e.set_footer(text="ID: {}".format(role.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        ch = await self.get_logs_channel(role.guild.id)
        if not ch:
            return

        guild = await self.bot.get_guild_settings(role.guild.id)
        lang = self.bot.get_language_object(guild.language)

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create):
                if entry.target == role:
                    moderator = entry.user

            try:
                text = lang['role_deleted_by'].format(role.mention, moderator.mention)
            except UnboundLocalError:
                text = lang['role_deleted'].format(f'**{role}**')
        except discord.Forbidden:
            text = lang['role_deleted'].format(f'**{role}**')

        e = discord.Embed(description=text,
                          color=0xa86623,
                          timestamp=role.created_at)

        e.set_author(name=role.guild, icon_url=role.guild.icon_url)
        e.set_footer(text="ID: {}".format(role.id))

        await ch.send(embed=e)

    # todo
    # @commands.Cog.listener()
    # async def on_guild_role_update(self, before, after):
    #     ch = await self.get_logs_channel(after.guild.id)
    #     if not ch:
    #         return
    #
    #     if before.name != after.name:
    #
    #         text = _(await get_language(self.bot, after.guild.id),
    #                  "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)
    #
    #         try:
    #             async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update):
    #                 if entry.target.id == after.id:
    #                     moderator = entry.user
    #
    #                     text = _(await get_language(self.bot, after.guild.id),
    #                              "Nazwa roli zmieniona z {} na {} przez {}.").format(before.name, after.name,
    #                                                                                  moderator.mention)
    #                 else:
    #                     text = _(await get_language(self.bot, after.guild.id),
    #                              "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)
    #         except discord.Forbidden:
    #             text = _(await get_language(self.bot, after.guild.id),
    #                      "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)
    #
    #     elif before.hoist is not after.hoist:
    #         if after.hoist:
    #             text = _(await get_language(self.bot, after.guild.id),
    #                      "Od teraz rola {} jest wyświetlana osobno.").format(after.mention)
    #         else:
    #             text = _(await get_language(self.bot, after.guild.id),
    #                      "Rola {} nie jest już wyświetlana osobno.").format(after.mention)
    #
    #     elif before.color != after.color:
    #         text = _(await get_language(self.bot, after.guild.id),
    #                  "Przed: {}\nPo: {}").format(str(before.color),
    #                                              str(after.color))
    #
    #     if not text:
    #         return
    #
    #     e = discord.Embed(description=text,
    #                       color=0xa86623,
    #                       timestamp=before.created_at)
    #     e.set_author(name=after.guild, icon_url=after.guild.icon_url)
    #     e.set_footer(text="ID: {}".format(after.id))
    #
    #     await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        ch = await self.get_logs_channel(guild.id)
        if not ch:
            return

        emote = None

        for emoji in before:
            if emoji not in after:
                emote = emoji
                break

        if not emote:
            return

        guild = await self.bot.get_guild_settings(guild.id)
        lang = self.bot.get_language_object(guild.language)

        e = discord.Embed(description=lang['emote_added'].format(str(emote)),
                          color=0x6e100a,
                          timestamp=emote.created_at)

        e.set_author(name=guild, icon_url=guild.icon_url)

        await ch.send(embed=e)


def setup(bot):
    bot.add_cog(Logs(bot))
