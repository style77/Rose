import json

import asyncpg
from discord.ext import commands

from ..utils.misc import get_prefix
from ..utils.DEFAULTS import HEARTBOARD_EMOJI, STARS_COUNT, WARNS_KICK


class Guild:
    """Base class for Rose's Guild representation."""
    def __init__(self, bot, req):
        self.data = req
        self.bot = bot

        self.online_queue = []
        self.online_top_update = 2

        self.guild_obj = bot.get_guild(req['guild_id'])
        self.id = req['guild_id']

    def __str__(self):
        return f"<Guild guild_id={self['guild_id']} prefix={self.prefix}>"

    def __repr__(self):
        return self.__str__()

    def __getitem__(self, item):
        return self.data.get(item, None)

    def __iter__(self):
        return self.data.items()

    @property
    def prefix(self):
        return self.data['prefix']

    @property
    def lang(self):
        return self.data['lang']

    @property
    def language(self):
        return self.lang

    @property
    def welcome_text(self):
        return self.data['welcome_text']

    @property
    def welcome_channel(self):
        return self.data['welcome_channel']

    @property
    def leave_text(self):
        return self.data['leave_text']

    @property
    def leave_channel(self):
        return self.data['leave_channel']

    @property
    def leveling_type(self):
        return self.data['leveling_type']

    @property
    def levels(self):
        return self.data['levels']

    @property
    def security(self):
        return json.loads(self.data['security'])

    @property
    def stars(self):
        return json.loads(self.data['stars'])

    @property
    def stats(self):
        return json.loads(self.data['stats'])

    def get_starboard(self):
        return self.bot.get_channel(self.stars['starboard']) or None

    def get_auto_role(self):
        return self.guild_obj.get_role(self.data['auto_role']) or None

    def get_mute_role(self):
        return self.guild_obj.get_role(self.data['mute_role']) or None

    async def get_blocked_cogs(self):
        return self['blocked_cogs'] or []

    async def get_blocked_commands(self):
        return self['blocked_commands'] or []

    async def update_cache(self):
        if self.id in self.bot._settings_cache:
            raw_guild_settings = await self.bot.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", self.id)
            if raw_guild_settings is None:
                raw_guild_settings = await self.bot.add_guild_to_database(self.id)
            g = Guild(self.bot, raw_guild_settings)
            self.bot._settings_cache[self.id] = g

    async def set(self, key, value, *, table="guild_settings"):
        try:
            z = await self.bot.db.execute(f"UPDATE {table} SET {key} = $1 WHERE guild_id = $2", value, self.id)
        except Exception as e:
            return print(e)
        await self.update_cache()
        return z

    async def set_security(self, key, value, *, base=None, table="guild_settings"):
        sec = self.security
        try:
            if base:
                sec[base][key] = value
            else:
                sec[key] = value
        except KeyError:
            return False
        z = await self.bot.db.execute(f"UPDATE {table} SET security = $1 WHERE guild_id = $2", json.dumps(sec), self.id)
        await self.update_cache()
        return z

    async def set_stars(self, key, value, *, table="guild_settings"):
        sec = self.stars

        try:
            sec[key] = value
        except KeyError:
            return False

        await self.bot.db.execute(f"UPDATE {table} SET stars = $1 WHERE guild_id = $2", json.dumps(sec), self.id)
        await self.update_cache()
        return True

    async def set_stats(self, base, key, value, *, table="guild_settings"):
        sec = self.stats

        # if base == 'online_top':
        #     if self.online_top_update == 0:
        #         print('updating')
        #         for func in self.online_queue:
        #             await func
        #             self.online_queue.remove(func)
        #         self.online_top_update = 2
        #     else:
        #         print('adding to q')
        #         self.online_queue.append(self.bot.db.execute(f"UPDATE {table} SET stats = $1 WHERE guild_id = $2", json.dumps(sec), self.id))
        #         print(self.online_queue)
        #         self.online_top_update -= 1

        try:
            sec[base][key] = value
        except KeyError:
            return False

        await self.bot.db.execute(f"UPDATE {table} SET stats = $1 WHERE guild_id = $2", json.dumps(sec), self.id)
        await self.update_cache()
        return True

    async def set_plugin(self, plugin, on):
        if not plugin.is_turnable():
            raise commands.BadArgument(f"{plugin.qualified_name} is not possible to turn off/on")

        plugins = await self.bot.db.fetchrow("SELECT blocked_cogs FROM guild_settings WHERE guild_id = $1", self.id)

        if on:
            if plugin.name not in plugins[0]:
                raise commands.BadArgument("This plugin is already on.")
            plugins[0].remove(plugin.name)

        elif plugin.name in plugins[0]:
            raise commands.BadArgument("This plugin is already off.")
        else:
            plugins[0].append(plugin.name)
        await self.bot.db.execute("UPDATE guild_settings SET blocked_cogs = $1 WHERE guild_id = $2", plugins[0],
                                  self.id)
        await self.update_cache()
