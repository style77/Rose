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

        e = discord.Embed(description=_(await get_language(self.bot, m.guild.id),
                                        "**Wiadomość wysłana przez {} w {} została usunięta.**\n{}").format(
            m.author.mention, m.channel.mention, m.content),
            color=0xb8352c,
            timestamp=m.created_at)
        e.set_author(name=m.author, icon_url=m.author.avatar_url)
        e.set_footer(text=f"ID: {m.author.id}")

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, m):
        # in bulk_message_delete event arg m is list of messages, not one message object or bulk message object
        # that's why we cant get its author and I have to set author after using some of mod commands that are specified
        # in mod_commands.
        # P.S. Im little scared that this will be bugged and people could get people from other server as
        # command authors but we will see.

        # P.S. 2 I have changed this and now its not getting author, instead mod_command_use is invoked and there i can
        # get author so its perfect
        if not m[0].guild:
            return

        ch = await self.get_logs_channel(m[0].guild.id)

        e = discord.Embed(description=_(await get_language(self.bot, m[0].guild.id),
                                        "**{} wiadomości usuniętych w {}.**").format(len(m) - 1, m[0].channel.mention),
                          color=0x6e100a,
                          timestamp=m[0].created_at)
        e.set_author(name=m[0].guild, icon_url=m[0].guild.icon_url)

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not after.guild:
            return
        ch = await self.get_logs_channel(after.guild.id)

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
        e.set_author(name=after.author, icon_url=after.author.avatar_url)
        e.set_footer(text="ID: {}".format(after.author.id))

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_mod_command_use(self, ctx):
        if not ctx.guild:
            return

        ch = await self.get_logs_channel(ctx.guild.id)

        e = discord.Embed(description=_(await get_language(self.bot, ctx.guild.id),
                                        "{} użył komendy `{}`.").format(ctx.author.mention, ctx.command.name),
                          color=discord.Color.blurple(),
                          timestamp=ctx.message.created_at)

        e.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
        e.set_footer(text="ID: {}".format(ctx.author.id))

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_prefix_change(self, ctx, new_prefix):
        if not ctx.guild:
            return

        ch = await self.get_logs_channel(ctx.guild.id)

        e = discord.Embed(description=_(await get_language(self.bot, ctx.guild.id),
                                        "{} zmienił prefix na `{}`.").format(ctx.author.mention, new_prefix),
                          color=discord.Color.blurple(),
                          timestamp=ctx.message.created_at)

        e.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        e.set_footer(text="ID: {}".format(ctx.author.id))

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        ch = await self.get_logs_channel(member.guild.id)

        e = discord.Embed(description=_(await get_language(self.bot, member.guild.id),
                                        "{} ({}) dołaczył do `{}`.\nKonto stworzone: `{}`.").format(member.mention,
                                                                                                    member,
                                                                                                    member.guild.name,
                                                                                                    str(
                                                                                                        member.created_at)),
                          color=discord.Color.green(),
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        ch = await self.get_logs_channel(member.guild.id)

        e = discord.Embed(description=_(await get_language(self.bot, member.guild.id),
                                        "{} ({}) opuścił serwer.\nDołączył: `{}`.").format(member.mention, member,
                                                                                           member.joined_at),
                          color=0x6e100a,
                          timestamp=member.joined_at)

        e.set_author(name=member, icon_url=member.avatar_url)

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        ch = await self.get_logs_channel(guild.id)

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

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        ch = await self.get_logs_channel(guild.id)

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

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_member_update(self, before, update):
        pass

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        ch = await self.get_logs_channel(role.guild.id)

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

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        ch = await self.get_logs_channel(role.guild.id)

        try:
            async for entry in role.guild.audit_logs(action=discord.AuditLogAction.role_delete):
                if entry.target.id == role.id:
                    moderator = entry.user

            try:
                text = _(await get_language(self.bot, role.guild.id),
                         "Rola {} usunięta przez {}.").format(f'**{role}**', moderator.mention)
            except UnboundLocalError:
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

        if ch:
            await ch.send(embed=e)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        pass

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        ch = await self.get_logs_channel(guild.id)

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

        e.set_author(name=guild, icon_url=guild.avatar_url)

        if ch:
            await ch.send(embed=e)

def setup(bot):
    bot.add_cog(Logs(bot))
