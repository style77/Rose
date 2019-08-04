import discord
from discord.ext import commands

class Context(commands.Context):
    def __init__(self, **kwargs):
        self._db = None


