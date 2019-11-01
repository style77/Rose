import json

import discord
from discord.ext import commands


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


class EmojiConverter(commands.Converter):
    async def convert(self, ctx, argument):
        em = await commands.EmojiConverter().convert(ctx, argument)
        if not em:
            em = await commands.PartialEmojiConverter().convert(ctx, argument)
            if not em:
                with open(r'cogs/utils/emoji_map.json', 'r') as f:
                    line = json.load(f)
                if argument in line.values():
                    return argument
                else:
                    raise commands.BadArgument()

        return f"<:{em.name}:{em.id}>"
