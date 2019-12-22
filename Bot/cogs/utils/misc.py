import io
import zlib

from yaml import load, Loader

from discord.utils import escape_markdown, escape_mentions
from discord import Guild
from .DEFAULTS import LANGUAGE


def clean_text(text):
    z = escape_markdown(text)
    z = escape_mentions(z)
    return z


async def get_prefix(bot, message):
    if not message.guild:
        return ""

    guild_settings = await bot.get_guild_settings(message.guild.id)

    if not guild_settings:
        return "/"

    if bot.development and message.guild.id in [515159795473317889, 480720960710901771, 538366293921759233]:
        return '!'

    return [f"{guild_settings.prefix} ", guild_settings.prefix]


def get(thing):
    with open(r"config.yml", 'r') as f:
        cfg = load(f, Loader=Loader)
    return cfg[thing]


async def get_language(bot, guild):
    if isinstance(guild, int):
        guild_id = guild
    elif isinstance(guild, Guild):
        guild_id = guild.id

    if not guild:
        return LANGUAGE

    guild_settings = await bot.get_guild_settings(guild_id)
    if not guild_settings:
        return LANGUAGE

    return guild_settings.lang


def transform_arguments(text, member):
    if "<@USER>" in text:
        text = text.replace("<@USER>", member.mention)

    if "<USER>" in text:
        text = text.replace("<USER>", member.name)

    if "<USER.JOINED_AT>" in text:
        text = text.replace("<USER.JOINED_AT>", str(member.joined_at))

    if "<USER.CREATED>" in text:
        text = text.replace("<USER.CREATED>", str(member.created_at))

    if "<USER.ID>" in text:
        text = text.replace("<USER.ID>", str(member.id))

    if "<USER#DISCRIM>" in text:
        text = text.replace("<USER#DISCRIM>", str(member))

    if "<USER.DISCRIM>" in text:
        text = text.replace("<USER.DISCRIM>", str(member.discriminator))

    if "<GUILD>" in text:
        text = text.replace("<GUILD>", member.guild.name)

    if "<GUILD.ID>" in text:
        text = text.replace("<GUILD.ID>", str(member.guild.id))

    return text


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')
