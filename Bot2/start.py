import asyncio
import json
import os

from cogs.classes.bot import Bot
from cogs.utils.misc import get_language

os.environ["JISHAKU_HIDE"] = "1"
os.environ["JISHAKU_NO_UNDERSCORE"] = "1"
os.environ["JISHAKU_RETAIN"] = "1"

bot = Bot()


@bot.before_invoke
async def context_creator(ctx):
    bot.context = ctx

bot.exts = ['jishaku', 'owner', 'eh', 'fun', 'todo', 'social', 'events', 'miscellaneous', 'moderator', 'music', 'logs',
            'nsfw&sfw', 'streams', 'cat', 'stars', 'gamestats', 'help']


if '__main__' == __name__:
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.start(bot._config['token']))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.logout())
    finally:
        loop.close()
