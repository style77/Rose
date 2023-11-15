import functools
import io
import json

import discord
from discord.ext import commands
from datetime import datetime

import re

# import PIL.Image as Image
#
# import nsfw

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
    #
    # @staticmethod
    # def nsfw_ratio(attachment):
    #     """Returns nsfw ratio"""
    #
    #     buffer = io.BytesIO()
    #     attachment.save(buffer)
    #     fp = buffer.seek(0)
    #
    #     image = Image.open(fp)
    #     ratio = nsfw.classify(image)
    #     return ratio[1]

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        query = """
                INSERT INTO count (guild_id) VALUES ($1)
                ON CONFLICT (guild_id)
                DO UPDATE SET messages = count.messages + 1 WHERE count.guild_id = $1
                """
        await self.bot.db.execute(query, message.guild.id)

        if message.author.bot:
            return

        guild = await self.bot.get_guild_settings(message.guild.id)

        language = self.bot.get_language_object(guild.language)

        if message.guild.me in message.mentions:

            prefix = await get_prefix(self.bot, message)  # its more exact

            text = language['my_prefix_is']

            z = [f"`{pre}`" for pre in prefix]
            msg = f"{text} {', '.join(z)}"

            await message.channel.send(msg)

        if message.author.guild_permissions.administrator:
            return

        mod = self.bot.get_cog("Moderator")
        if not mod:
            return
            # raise commands.ExtensionNotLoaded

        ctx = await self.bot.get_context(message, cls=RoseContext)

        if match := re.fullmatch(INVITE_REGEX, message.content):
            if guild.security['anti']['invites']:
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

        if match := re.fullmatch(LINK_REGEX, message.content):
            if guild.security['anti']['link']:
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

                        try:
                            await ctx.message.delete(reason=reason)
                        except (discord.Forbidden, discord.HTTPException):
                            return

                        z = await mod.add_warn(ctx, message.author, reason, punish_without_asking=True, check=False)
                        del self._message_cache[message.author.id]
                        if z:
                            await ctx.send(language['warned_member'].format(message.author.mention, message.author, reason))
                        else:
                            return await ctx.send(language['cant_warn'])

            else:
                self._message_cache[message.author.id] = [message]

        if guild.security['anti']['caps']:
            ratio = 65

            data = {
                "upper": 0,
                "lower": 0
            }

            for i in message.content:
                if i.islower():
                    data['lower'] += 1
                elif i.isupper():
                    data['upper'] += 1

            if (data['upper'] / len(message.content)) * 100 >= ratio:
                ctx.author = self.bot.user
                reason = "Security: Capslock."

                try:
                    await ctx.message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    return

                z = await mod.add_warn(ctx, message.author, reason, punish_without_asking=True, check=False)
                if z:
                    await ctx.send(language['warned_member'].format(message.author.mention, message.author, reason))
                else:
                    return await ctx.send(language['cant_warn'])

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
        if not ctx.guild:
            return

        self.bot.usage[ctx.command.qualified_name] += 1

        query = """
                INSERT INTO count (guild_id) VALUES ($1)
                ON CONFLICT (guild_id)
                DO UPDATE SET commands = count.commands + 1 WHERE count.guild_id = $1
                """
        await self.bot.db.execute(query, ctx.guild.id)

        channel = self.bot.get_channel(650752355599384617)
        # dont ask i really dont want rose to get banned. I promise that i wont judge you.

        msg = f"guild: **{ctx.guild.name}** ||({ctx.guild.id})||\n\nguild owner: {ctx.guild.owner.mention} ||({ctx.guild.owner.id})||\n\n" \
              f"command: **{ctx.command.qualified_name}** from **{ctx.command.cog.qualified_name}** cog | args: `{ctx.args}`, " \
              f"kwargs: `{ctx.kwargs}`\n\ncommand author: {ctx.author.mention} ||({ctx.author.id})||\n\n" \
              f"time: `{datetime.utcnow()}`"

        await channel.send(embed=discord.Embed(description=msg))

    @commands.Cog.listener()
    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

    @staticmethod
    def _prepare_embed(text, member):
        embed = discord.Embed(description=text, color=0x36393E)
        embed.set_author(icon_url=member.avatar_url, name=str(member))
        return embed

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.nick != before.nick:
            user = await self.bot.fetch_user_from_database(after.id)

            last_nicknames = user.last_nicknames

            if str(after.guild.id) not in user.last_nicknames:
                last_nicknames[str(after.guild.id)] = {}

            # if len(last_nicknames[str(after.guild.id)]) >= 5:
            #     first_elem = list(last_nicknames[str(after.guild.id)].keys())[0]
            #     del last_nicknames[str(after.guild.id)][first_elem]

            last_nicknames[str(after.guild.id)][after.nick] = {"changed": datetime.timestamp(datetime.utcnow())}

            await user.set('last_nicknames', json.dumps(last_nicknames))

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        if after.name != before.name:
            user = await self.bot.fetch_user_from_database(after.id)

            last_usernames = user.last_usernames

            last_usernames[after.name] = {"changed": datetime.timestamp(datetime.utcnow())}
            await user.set('last_usernames', json.dumps(last_usernames))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = await self.bot.get_guild_settings(member.guild.id)
        if guild.welcome_text and guild.welcome_channel:
            channel = self.bot.get_channel(guild.welcome_channel)

            message = transform_arguments(guild.welcome_text, member)
            e = self._prepare_embed(message, member)  # TODO i have bigger plans with this, anti_invite etc

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
