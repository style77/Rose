import discord
from discord.ext import commands

from .classes.converters import EmojiConverter
from .classes.plugin import Plugin


class RR(Plugin):
    def __init__(self, bot):
        self.bot = bot

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

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def rr(self, ctx):
        """Reaction role."""
        z = []
        for cmd in self.bot.get_command("rr").commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz ustawić:\n```\n{}```").format('\n'.join(z)))

    @rr.command()
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, channel: discord.TextChannel = None, msg_id: int = None, role: discord.Role = None,
                  emoji: EmojiConverter = None):
        """Dodaje reaction role do podanej wiadomości."""
        if not channel or not msg_id or not role:
            raise commands.UserInputError()

        if not emoji:
            return await ctx.send(_(ctx.lang, "Ta emotka nie jest poprawna."))

        message = await channel.fetch_message(msg_id)

        if not message:
            return await ctx.send(_(ctx.lang, "Ta wiadomość nie istnieje."))

        await message.add_reaction(emoji)
        await ctx.send(":ok_hand:")
        await self.bot.pg_con.execute(
            'INSERT INTO rr (guild_id, message_id, channel_id, role_id, emoji) VALUES ($1, $2, $3, $4, $5)',
            ctx.guild.id, msg_id, channel.id, role.id, str(emoji))

    @rr.command()
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, channel: discord.TextChannel = None, msg_id: int = None, emoji: EmojiConverter = None):
        """Usuwa wyznaczoną emotkę z rr."""
        if not channel or not msg_id:
            raise commands.UserInputError()
        if not emoji:
            return await ctx.send(_(ctx.lang, "Ta emotka nie jest poprawna."))
        rr = await self.bot.pg_con.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                         ctx.guild.id, msg_id, str(emoji))
        if not rr:
            return await ctx.send(
                _(ctx.lang, "Takie reaction role nie istnieje. Sprawdź poprawność wszystkich argumentów."))
        await self.bot.pg_con.execute(
            'DELETE FROM rr WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3 AND emoji = $4', ctx.guild.id,
            channel.id, msg_id, str(emoji))
        await ctx.send(':ok_hand:')

    @rr.command()
    @commands.has_permissions(manage_guild=True)
    async def clear(self, ctx, channel: discord.TextChannel = None, msg_id: int = None):
        """Usuwa wszystkie rr z wiadomości."""
        if not channel or not msg_id:
            raise commands.UserInputError()
        rr = await self.bot.pg_con.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2", ctx.guild.id,
                                         msg_id)
        if not rr:
            return await ctx.send(
                _(ctx.lang, "Takie reaction role nie istnieje. Sprawdź poprawność wszystkich argumentów."))
        await self.bot.pg_con.execute('DELETE FROM rr WHERE guild_id = $1 AND channel_id = $2 AND message_id = $3',
                                      ctx.guild.id, channel.id, msg_id)
        await ctx.send(':ok_hand:')

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id:
            return
        message = await self.bot.pg_con.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                              payload.guild_id, payload.message_id, payload.emoji.name)
        if not message:
            return
        member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        await self.update_role('add', payload.guild_id, member, message[0]['role_id'])

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        message = await self.bot.pg_con.fetch("SELECT * FROM rr WHERE guild_id = $1 AND message_id = $2 AND emoji = $3",
                                              payload.guild_id, payload.message_id, payload.emoji.name)
        if not message:
            return
        member = self.bot.get_guild(payload.guild_id).get_member(payload.user_id)
        await self.update_role('remove', payload.guild_id, member, message[0]['role_id'])


def setup(bot):
    bot.add_cog(RR(bot))
