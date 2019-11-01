import re

import discord
from discord.ext import commands


class RoseContext(commands.Context):
    async def add_react(self, type_: bool):
        emoji = '<:checkmark:601123463859535885>' if type_ is True else '<:wrongmark:601124568387551232>'
        if '<:checkmark:601123463859535885>' in self.message.reactions or '<:wrongmark:601124568387551232>' in self.message.reactions:
            return

        try:
            await self.message.add_reaction(emoji)
        except discord.HTTPException:
            return

    async def confirm(self, confirmation, member, *, _type="reaction", prompt=None):
        if _type == "reaction":
            msg = await self.message.send(confirmation)

            reactions = ['<:checkmark:601123463859535885>', '<:wrongmark:601124568387551232>']

            for r in reactions:
                await msg.add_reaction(r)

            def check(reaction, user):
                return reaction in reactions and user == member

            reaction, user = await self.bot.wait_for('reaction_add', check=check)

            if reaction == reactions[0]:
                return True
            elif reaction == reactions[1]:
                return False
            else:
                return False

        elif _type == "message":

            if not prompt:
                raise ValueError("No prompt passed.")

            msg = await self.message.send(confirmation)

            def check(m):
                return m.author == member and m.channel == msg.channel

            message = await self.bot.wait_for('message', check=check)

            if message.content.lower() == prompt.lower():
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
