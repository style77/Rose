import json
import re

import discord
from discord.ext import commands


class AmountConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.isdigit() or argument in ['all']:
            return argument
        return 1


class ModerationReason(commands.Converter):
    async def convert(self, ctx, argument):
        return f"[{ctx.author}]: {argument}"[:512]


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        ban_list = await ctx.guild.bans()
        try:
            member_id = int(argument, base=10)
            entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
        except ValueError:
            entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)
        if entity is None:
            raise commands.UserInputError()
        return entity


class SafeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = discord.utils.escape_markdown(argument)
        argument = discord.utils.escape_mentions(argument)
        return argument


time_regex = re.compile(r"(?:(\d{1,5})(h|hr|hrs|s|sec|m|min|d|w|mo|y))+?")
time_dict = {"h": 3600, "hr": 3600, "hrs": 3600, "s": 1, "sec": 1, "min": 60, "m": 60,
             "d": 86400, "y": 31536000, "mo": 2592000, "w": 604800}


class VexsTimeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        args = argument.lower()
        matches = re.findall(time_regex, args)
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise commands.BadArgument("{} is an invalid time-key! h/m/s/d are valid!".format(k))
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time


class EmojiConverter(commands.Converter):
    async def convert(self, ctx, argument):
        em = None

        try:
            em = await commands.EmojiConverter().convert(ctx, argument)
        except commands.BadArgument:
            pass

        if not em:
            try:
                em = await commands.PartialEmojiConverter().convert(ctx, argument)
            except commands.BadArgument:
                pass

        if not em:
            with open(r'assets/other/emoji_map.json', 'r') as f:
                line = json.load(f)
                if argument in line.values():
                    return argument
                else:
                    raise commands.BadArgument()
        else:
            if not discord.utils.find(lambda emoji_: emoji_.id == em.id, ctx.bot.emojis):
                raise commands.BadArgument(f"Emoji \"{argument}\" not found.")

            if em.animated:
                emoji = f"<a:{em.name}:{em.id}>"
            else:
                emoji = f"<:{em.name}:{em.id}>"
            return emoji


class ValueRangeFromTo(commands.Converter):
    def __init__(self, from_, to):
        self.from_ = from_
        self.to = to

    async def convert(self, ctx, argument: int):
        if self.from_ < int(argument) < self.to:
            return int(argument)
        return None
