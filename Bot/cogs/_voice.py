import discord
from discord.ext import commands
import typing
import speech_recognition as sr
import asyncio

"""Currently its not possible to do this. 
    Im sorry."""


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def join(self, ctx, channel: typing.Optional[discord.VoiceChannel]=None):
        channel = ctx.author.voice.channel or channel
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)

        await channel.connect()
        while True:
            r = sr.Recognizer()
            with sr.Microphone() as source:
                audio = r.listen(source)
            print(r.recognize_google(audio, language='pl'))

def setup(bot):
    bot.add_cog(Voice(bot))
