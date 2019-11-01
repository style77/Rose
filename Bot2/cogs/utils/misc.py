from yaml import load, Loader

from discord.utils import escape_markdown, escape_mentions
from .DEFAULTS import LANGUAGE


def clean_text(text):
    z = escape_markdown(text)
    z = escape_mentions(z)
    return z


async def get_prefix(bot, message):
    if not message.guild:
        return ""

    prefix = await bot.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", message.guild.id)

    if not prefix:
        return "/"

    if bot.development:
        return '!'

    return [f"{prefix['prefix']} ", prefix['prefix']]


def get(thing):
    with open(r"config.yml", 'r') as f:
        cfg = load(f, Loader=Loader)
    return cfg[thing]


async def get_language(bot, guild):
    if not guild:
        return LANGUAGE

    lang = await bot.db.fetchrow("SELECT lang FROM guild_settings WHERE guild_id = $1", guild.id)
    if not lang:
        return LANGUAGE

    return lang[0]


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
