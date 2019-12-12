import discord
from discord.ext import commands

import re

from .classes.context import RoseContext
from .classes.other import Plugin
from .utils.misc import transform_arguments, get_prefix

INVITE_REGEX = re.compile(r"(?:https?://)?discord(?:app\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")
LINK_REGEX = re.compile(r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,4}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)")


class Events(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

        self._message_cache = dict()

    @commands.Cog.listener()
    async def on_guild_remove(self, g):
        e = discord.Embed(
            description=f"Usunięto **{g.name}**\nWłaściciel: {g.owner.mention} (**{g.owner.name}**)\nAktualna liczba "
                        f"serwerów: {len(self.bot.guilds)}",
            color=discord.Color.dark_red())
        e.set_author(name="Usunięto serwer", icon_url=g.icon_url)
        await self.bot.get_channel(610827984668065802).send(embed=e)

        await self.bot.clear_settings(g.id)

    @commands.Cog.listener()
    async def on_guild_join(self, g):
        e = discord.Embed(
            description=f"Dodano **{g.name}**\nWłaściciel: {g.owner.mention} (**{g.owner.name}**)\nAktualna liczba "
                        f"serwerów: {len(self.bot.guilds)}",
            color=discord.Color.green())
        e.set_author(name="Dodano serwer", icon_url=g.icon_url)
        await self.bot.get_channel(610827984668065802).send(embed=e)

        await self.bot.get_guild_settings(g.id)

        for channel in g.text_channels:
            try:
                await channel.send(f"{self.bot.english['hey_im']} {self.bot.user.name}. {self.bot.english['ty_for_adding']}")
                break
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if message.author.guild_permissions.administrator:
            return

        guild = await self.bot.get_guild_settings(message.guild.id)

        language = self.bot.polish if guild.language == "PL" else self.bot.english

        mod = self.bot.get_cog("Moderator")
        if not mod:
            return
            # raise commands.ExtensionNotLoaded

        ctx = await self.bot.get_context(message, cls=RoseContext)

        if guild.security['anti']['invites']:  # todo on_member_join check if member nick is not invite
            match = re.fullmatch(INVITE_REGEX, message.content)
            if match:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

                ctx.author = message.guild.me
                reason = "Security: Sending invites."

                z = await mod.add_warn(ctx, message.author, reason, punish_without_asking=True, check=False)
                if z:
                    await ctx.send(language['warned_member'].format(message.author.mention, message.author, reason))
                else:
                    return await ctx.send(language['cant_warn'])

        if guild.security['anti']['link']:
            match = re.fullmatch(LINK_REGEX, message.content)
            if match:
                try:
                    await message.delete()
                except discord.HTTPException:
                    pass

                ctx.author = message.guild.me
                reason = "Security: Sending links."

                z = await mod.add_warn(ctx, message.author, reason, punish_without_asking=True, check=False)
                if z:
                    await ctx.send(language['warned_member'].format(message.author.mention, message.author, reason))
                else:
                    return await ctx.send(language['cant_warn'])

        if guild.security['anti']['spam']:

            if message.author.id in self._message_cache:
                last = self._message_cache[message.author.id][-1]  # last component of list

                if last.content != message.content:
                    del self._message_cache[message.author.id]

                else:
                    self._message_cache[message.author.id].append(message)

                    if len(self._message_cache[message.author.id]) >= guild.security['spam_messages']:

                        # mod = self.bot.get_cog('moderator')
                        # if not mod:
                        #     raise commands.ExtensionNotLoaded

                        ctx.author = self.bot.user
                        reason = "Security: Spam."

                        z = await mod.add_warn(ctx, message.author, reason, punish_without_asking=True, check=False)
                        del self._message_cache[message.author.id]
                        if z:
                            await ctx.send(language['warned_member'].format(message.author.mention, message.author, reason))
                        else:
                            return await ctx.send(language['cant_warn'])

            else:
                self._message_cache[message.author.id] = [message]

        if message.content.lower() in ["<@573233127556644873>", "<@573233127556644873> prefix", "<@!573233127556644873>",
                                       "<@!573233127556644873> prefix"]:

            prefix = await get_prefix(self.bot, message)  # its more exact

            if guild.lang == "PL":
                lang = self.bot.polish['my_prefix_is']

            elif guild.lang == "ENG":
                lang = self.bot.english['my_prefix_is']

            else:
                # if stuff doesnt work, i found that people usually try mentioning bot to get
                # some info, that's why i added this only here

                raise commands.BadArgument("Language set on this server is wrong.\nPlease join support server to "
                                           "fix this issue.")

            z = []
            for pre in prefix:
                z.append(f"`{pre}`")
            msg = f"{lang} {', '.join(z)}"

            await message.channel.send(msg)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = await self.bot.get_guild_settings(member.guild.id)
        role = await guild.get_auto_role()
        if not role:
            return

        try:
            await member.add_roles(role, reason="Auto Role.")
        except (discord.Forbidden, discord.HTTPException):
            return

    @commands.Cog.listener()
    async def on_command(self, ctx):
        self.bot.usage[ctx.command.qualified_name] += 1

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

    @staticmethod
    def _prepare_embed(text, member):
        embed = discord.Embed(description=text, color=0x36393E)
        embed.set_author(icon_url=member.avatar_url, name=str(member))
        return embed

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = await self.bot.get_guild_settings(member.guild.id)
        if guild.welcome_text and guild.welcome_channel:
            channel = self.bot.get_channel(guild.welcome_channel)

            message = transform_arguments(guild.welcome_text, member)
            e = self._prepare_embed(message, member)  # TODO i have bigger plans with this

            await channel.send(embed=e)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        guild = await self.bot.get_guild_settings(member.guild.id)
        if guild.leave_text and guild.leave_channel:
            channel = self.bot.get_channel(guild.leave_channel)

            message = transform_arguments(guild.leave_text, member)
            e = self._prepare_embed(message, member)  # TODO i have bigger plans with this - online embed creator

            await channel.send(embed=e)


def setup(bot):
    bot.add_cog(Events(bot))
