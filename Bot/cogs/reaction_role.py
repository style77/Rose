import discord
from discord.ext import commands

from .classes.converters import EmojiConverter
from .classes.other import Plugin


class ReactionRole(Plugin):

    async def cog_check(self, ctx):
        return ctx.guild is not None

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def rr(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @rr.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self,
                  ctx,
                  message: discord.Message,
                  role: discord.Role,
                  emoji: EmojiConverter):

        if not emoji:
            return await ctx.send(ctx.lang['bad_emoji'])

        if not message:
            return await ctx.send(ctx.lang['message_dont_exist'])

        rr = await self.bot.db.fetchrow("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                        ctx.guild.id, message.id, emoji)

        if rr:
            return await ctx.send(ctx.lang['that_rr_already_exist'])

        await message.add_reaction(emoji)

        query = "INSERT INTO rr (guild_id, message_id, channel_id, role_id, emoji) VALUES ($1, $2, $3, $4, $5)"
        await self.bot.db.execute(query, ctx.guild.id, message.id, message.channel.id, role.id, str(emoji))

        await ctx.send(ctx.lang['added_reaction_role'].format(message.jump_url, str(emoji), role.name, message.channel.mention))

    @rr.command(aliases=['delete'])
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, message: discord.Message, emoji: EmojiConverter):
        if not emoji:
            return await ctx.send(ctx.lang['bad_emoji'])

        rr = await self.bot.db.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                         ctx.guild.id, message.id, str(emoji))
        if not rr:
            return await ctx.send(ctx.lang['rr_dont_exist'])

        query = "DELETE FROM rr WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4"
        await self.bot.db.execute(query, ctx.guild.id, message.channel.id, message.id, str(emoji))
        await ctx.send(ctx.lang['removed_rr'].format(message.jump_url))
        try:
            await message.remove_reaction(emoji, ctx.guild.me)
        except discord.HTTPException:
            pass

    @rr.command(aliases=['purge'])
    @commands.has_permissions(manage_guild=True)
    async def clear(self, ctx, message: discord.Message):
        rr = await self.bot.db.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2", ctx.guild.id,
                                     message.id)
        if not rr:
            return await ctx.send(ctx.lang['rr_dont_exist'])

        c = await ctx.confirm(ctx.lang['confirm_rr_purge'].format(message.jump_url), ctx.author)
        if not c:
            return await ctx.send(ctx.lang['abort'])

        await self.bot.db.execute('DELETE FROM rr WHERE guild_id = $1 AND message_id = $2',
                                  ctx.guild.id, message.id)
        await ctx.send(ctx.lang['purged_rr'].format(message.jump_url))
        try:
            for reaction in [r['emoji'] for r in rr]:
                await message.remove_reaction(reaction, ctx.guild.me)
        except discord.HTTPException:
            pass

    async def update_role(self, toogle, guild_id, member, role_id):
        role = self.bot.get_guild(guild_id).get_role(role_id)
        if toogle == 'add':
            try:
                await member.add_roles(role)
            except discord.HTTPException:
                return
        elif toogle == 'remove':
            try:
                await member.remove_roles(role)
            except discord.HTTPException:
                return
        else:
            raise NotImplemented()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        message = await self.bot.db.fetchrow("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                             payload.guild_id, payload.message_id, payload.emoji.name)
        if not message:
            return

        member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        await self.update_role('add', payload.guild_id, member, message['role_id'])

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        message = await self.bot.db.fetchrow("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                             payload.guild_id, payload.message_id, payload.emoji.name)
        if not message:
            return

        member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        await self.update_role('remove', payload.guild_id, member, message['role_id'])


def setup(bot):
    bot.add_cog(ReactionRole(bot))