import asyncio
import json
import logging
import os

from cogs.classes.bot import Bot
from cogs.utils.misc import get_language

os.environ["JISHAKU_HIDE"] = "1"
os.environ["JISHAKU_NO_UNDERSCORE"] = "1"
os.environ["JISHAKU_RETAIN"] = "1"

bot = Bot()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
if bot.development:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.WARN)


@bot.before_invoke
async def context_creator(ctx):
    bot.context = ctx


bot.exts = ['owner', 'eh', 'fun', 'todo', 'social', 'events', 'miscellaneous', 'moderator', 'music', 'logs',
            'nsfw&sfw', 'streams', 'cat', 'stars', 'gamestats', 'help', 'stats', 'afk', 'tags', 'reaction_role',
            'private', 'emoji', 'tinder']

if '__main__' == __name__:
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot.start(bot._config['token']))
    except KeyboardInterrupt:
        loop.run_until_complete(bot.logout())
    finally:
        loop.run_until_complete(bot.db.close())
        bot.redis.close()
        loop.run_until_complete(bot.session.close())
        # for task in bot.tasks():
        #     task.close()
        loop.close()
