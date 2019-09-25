import discord

from discord.ext import commands
from .classes import cache, plugin


class Logs(plugin.Plugin):
    def __init__(self, bot):
        self.bot = bot

        # metadata
        self.author = None

    async def get_logs_channel(self, guild_id):
        logs_channel = cache.GuildSettingsCache().get(guild_id)
        if logs_channel:
            channel = self.bot.get_channel(logs_channel['database']['logs'])
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

        e = discord.Embed(description=_(await get_language(self.bot, m.guild.id),
                                        "**Wiadomość wysłana przez {} w {} została usunięta.**\n{}").format(
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
        # todo post all messages to hastebin
        if not m[0].guild:
            return

        ch = await self.get_logs_channel(m[0].guild.id)
        if not ch:
            return

        e = discord.Embed(description=_(await get_language(self.bot, m[0].guild.id),
                                        "**{} wiadomości usuniętych w {}.**").format(len(m) - 1, m[0].channel.mention),
                          color=0x6e100a,
                          timestamp=m[0].created_at)
        e.set_author(name=m[0].guild, icon_url=m[0].guild.icon_url)

        await ch.send(embed=e)

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

        e = discord.Embed(
            description=_(await get_language(self.bot, after.guild.id),
                          "Wiadomość została zeedytowana w {}\n[JUMP TO]({})").format(after.channel.mention,
                                                                                      after.jump_url),
            color=0xfabc11, timestamp=before.created_at)
        e.add_field(name=_(await get_language(self.bot, after.guild.id), "Przed"), value=before.content)
        e.add_field(name=_(await get_language(self.bot, after.guild.id), "Po"), value=after.content)

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

        e = discord.Embed(description=_(await get_language(self.bot, ctx.guild.id),
                                        "{} użył komendy `{}`.").format(ctx.author.mention, ctx.command.name),
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

        e = discord.Embed(description=_(await get_language(self.bot, ctx.guild.id),
                                        "{} zmienił prefix na `{}`.").format(ctx.author.mention, new_prefix),
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

        e = discord.Embed(description=_(await get_language(self.bot, member.guild.id),
                                        "{} ({}) dołaczył do `{}`.\nKonto stworzone: `{}`.").format(member.mention,
                                                                                                    member,
                                                                                                    member.guild.name,
                                                                                                    str(
                                                                                                        member.created_at)),
                          color=discord.Color.green(),
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        ch = await self.get_logs_channel(member.guild.id)
        if not ch:
            return

        e = discord.Embed(description=_(await get_language(self.bot, member.guild.id),
                                        "{} ({}) opuścił serwer.\nDołączył: `{}`.").format(member.mention, member,
                                                                                           member.joined_at),
                          color=0x6e100a,
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = await self.get_logs_channel(guild.id)
        if not ch:
            return

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user:
                    moderator = entry.user
                    reason = entry.reason if entry.reason else _(await get_language(self.bot, guild.id), 'Brak Powodu')

            try:
                text = _(await get_language(self.bot, guild.id),
                         "{} został zbanowany przez {} z powodu `{}`.").format(user.mention,
                                                                               moderator.mention,
                                                                               reason)
            except UnboundLocalError:
                text = _(await get_language(self.bot, guild.id),
                         "{} został zbanowany.").format(user.mention)
        except discord.Forbidden:
            text = _(await get_language(self.bot, guild.id),
                     "{} został zbanowany.").format(user.mention)

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

        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban):
                if entry.target == user:
                    moderator = entry.user
                    reason = entry.reason if entry.reason else _(await get_language(self.bot, guild.id), 'Brak Powodu')

            try:
                text = _(await get_language(self.bot, guild.id),
                         "{} został odbanowany przez {} z powodu `{}`.").format(user,
                                                                                moderator.mention,
                                                                                reason)
            except UnboundLocalError:
                text = _(await get_language(self.bot, guild.id),
                         "{} został odbanowany.").format(user)
        except discord.Forbidden:
            text = _(await get_language(self.bot, guild.id),
                     "{} został odbanowany.").format(user)

        e = discord.Embed(description=text,
                          color=0x22488a,
                          timestamp=user.created_at)

        e.set_author(name=user, icon_url=user.avatar_url)
        e.set_footer(text="ID: {}".format(user.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_update(self, before, update):
        pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        ch = await self.get_logs_channel(role.guild.id)
        if not ch:
            return

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_create):
                if entry.target == role:
                    moderator = entry.user

            try:
                text = _(await get_language(self.bot, role.guild.id),
                         "Rola {} utworzona przez {}.").format(role.mention, moderator.mention)
            except UnboundLocalError:
                text = _(await get_language(self.bot, role.guild.id),
                         "Rola {} utworzona.").format(role.mention)
        except discord.Forbidden:
            text = _(await get_language(self.bot, role.guild.id),
                     "Rola {} utworzona.").format(role.mention)

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

        text = _(await get_language(self.bot, role.guild.id),
                 "Rola {} usunięta.").format(f'**{role}**')

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user

                    text = _(await get_language(self.bot, role.guild.id),
                             "Rola {} usunięta przez {}.").format(f'**{role}**', moderator.mention)
                else:
                    text = _(await get_language(self.bot, role.guild.id),
                             "Rola {} usunięta.").format(f'**{role}**')
        except discord.Forbidden:
            text = _(await get_language(self.bot, role.guild.id),
                     "Rola {} usunięta.").format(f'**{role}**')

        e = discord.Embed(description=text,
                          color=0xa86623,
                          timestamp=role.created_at)

        e.set_author(name=role.guild, icon_url=role.guild.icon_url)
        e.set_footer(text="ID: {}".format(role.id))

        await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        ch = await self.get_logs_channel(after.guild.id)
        if not ch:
            return
        text = None

        if before.name != after.name:

            text = _(await get_language(self.bot, after.guild.id),
                     "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)

            try:
                async for entry in after.guild.audit_logs(action=discord.AuditLogAction.role_update):
                    if entry.target.id == after.id:
                        moderator = entry.user

                        text = _(await get_language(self.bot, after.guild.id),
                                 "Nazwa roli zmieniona z {} na {} przez {}.").format(before.name, after.name,
                                                                                     moderator.mention)
                    else:
                        text = _(await get_language(self.bot, after.guild.id),
                                 "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)
            except discord.Forbidden:
                text = _(await get_language(self.bot, after.guild.id),
                         "Nazwa roli zmieniona z {} na {}.").format(before.name, after.name)

        elif before.hoist is not after.hoist:
            if after.hoist:
                text = _(await get_language(self.bot, after.guild.id),
                         "Od teraz rola {} jest wyświetlana osobno.").format(after.mention)
            else:
                text = _(await get_language(self.bot, after.guild.id),
                         "Rola {} nie jest już wyświetlana osobno.").format(after.mention)

        elif before.color != after.color:
            text = _(await get_language(self.bot, after.guild.id),
                     "Przed: {}\nPo: {}").format(str(before.color),
                                                 str(after.color))

        if not text:
            return

        e = discord.Embed(description=text,
                          color=0xa86623,
                          timestamp=before.created_at)
        e.set_author(name=after.guild, icon_url=after.guild.icon_url)
        e.set_footer(text="ID: {}".format(after.id))

        await ch.send(embed=e)

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

        e = discord.Embed(description=_(await get_language(self.bot, guild.id),
                                        "Na serwer została dodana emotka {}.").format(str(emote)),
                          color=0x6e100a,
                          timestamp=emote.created_at)

        e.set_author(name=guild, icon_url=guild.icon_url)

        await ch.send(embed=e)


def setup(bot):
    bot.add_cog(Logs(bot))
