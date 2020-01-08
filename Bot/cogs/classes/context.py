import asyncio

import discord
from discord.ext import commands

from ..utils.paginator import Paginator


class RoseContext(commands.Context):
    def __init__(self, **attrs):
        super().__init__(**attrs)
        self.db = self.bot.db

    async def add_react(self, type_: bool, *, message=None):
        message = message or self.message
        emoji = '<:checkmark:601123463859535885>' if type_ is True else '<:wrongmark:601124568387551232>'
        reacts = [str(react) for react in message.reactions]
        if ('<:checkmark:601123463859535885>' or '<:wrongmark:601124568387551232>') in reacts:
            return

        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            return

    async def confirm(self, confirmation, member, *, type_="reaction", prompt=None, timeout=None):
        if type_ == "reaction":
            msg = await self.channel.send(confirmation)

            reactions = ['<:checkmark:601123463859535885>', '<:wrongmark:601124568387551232>']

            for r in reactions:
                await msg.add_reaction(r)

            def check(reaction, user):
                return user == member and reaction.message.id == msg.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=timeout)
            except asyncio.TimeoutError:
                return None

            if str(reaction) == "<:checkmark:601123463859535885>":
                return True
            elif str(reaction) == "<:wrongmark:601124568387551232>":
                return False
            else:
                return False

        elif type_ == "message":

            if not prompt:
                raise ValueError("No prompt.")

            msg = await self.channel.send(confirmation)

            def check(m):
                return m.author == member and m.channel == msg.channel

            try:
                message = await self.bot.wait_for('message', check=check, timeout=timeout)
            except asyncio.TimeoutError:
                return None

            if not isinstance(prompt, list):
                prompt = [prompt]

            if message.content.lower() in prompt:
                return True
            else:
                return False

        else:
            raise NotImplemented("This type of confirmation is not implemented.\nFeel free to suggest adding stuff on "
                                 f"support server (discord.gg/{self.bot._config['support_server']}) on "
                                 "#bikesheed channel.")

    # async def send(self, content=None, *args, **kwargs):
    #     if content is not None:
    #         content = await commands.clean_content().convert(self, str(content))
    #
    #         if kwargs.pop("escape_massmentions", True):
    #             content = content.replace("@here", "@\u200bhere").replace(
    #                 "@everyone", "@\u200beveryone"
    #             )
    #
    #     return await super().send(content, *args, **kwargs)

    async def paginate(self, **kwargs):
        await Paginator(**kwargs).paginate(self)
