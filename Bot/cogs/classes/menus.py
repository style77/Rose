import discord
from discord.ext import menus

EMOJIS_NUMBER = 11


class Switcher(menus.Menu):
    def __init__(self):
        super().__init__()

        self.number = -1

    async def send_initial_message(self, ctx, channel):
        return await channel.send(self._update_message(ctx.guild.emojis))

    def _update_message(self, emojis):
        z = ""
        for i in range(EMOJIS_NUMBER):
            z += str(emojis[self.number + i])
        return z

    @menus.button('\U000025c0')
    async def on_back(self, payload):
        if payload.event_type == "REACTION_ADD":
            guild = self.bot.get_guild(payload.guild_id)
            await self.message.edit(content=self._update_message(guild.emojis))
            self.number -= 1
            try:
                await self.message.remove_reaction('\U000025c0', payload.member)
            except discord.HTTPException:
                pass

    @menus.button('\U000025b6')
    async def on_forward(self, payload):
        if payload.event_type == "REACTION_ADD":
            guild = self.bot.get_guild(payload.guild_id)
            await self.message.edit(content=self._update_message(guild.emojis))
            self.number += 1
            try:
                await self.message.remove_reaction('\U000025b6', payload.member)
            except discord.HTTPException:
                pass

    @menus.button('\N{BLACK SQUARE FOR STOP}\ufe0f')
    async def on_stop(self, payload):
        self.stop()
