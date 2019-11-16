import json

from ..utils.misc import get_prefix
from ..utils.DEFAULTS import HEARTBOARD_EMOJI, STARS_COUNT, WARNS_KICK


class Guild(object):
    """Base class for Rose's Guild representation."""
    def __init__(self, bot, req):
        self.data = req
        self.bot = bot

        self.guild_obj = bot.get_guild(req['guild_id'])
        self.id = req['guild_id']

    def __getitem__(self, item):
        return self.data.get(item, None)

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
    def levels(self):
        return self.data['levels']

    @property
    def security(self):
        return json.loads(self.data['security'])

    @property
    def stars(self):
        return json.loads(self.data['stars'])

    def get_starboard(self):
        return self.bot.get_channel(self.stars['starboard']) or None

    def get_auto_role(self):
        return self.guild_obj.get_role(self.data['auto_role']) or None

    def get_mute_role(self):
        return self.guild_obj.get_role(self.data['mute_role']) or None

    async def update_cache(self):
        if self.id in self.bot._settings_cache:
            raw_guild_settings = await self.bot.db.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", self.id)
            if raw_guild_settings is None:
                raw_guild_settings = await self.bot.add_guild_to_database(self.id)
            g = Guild(self.bot, raw_guild_settings)
            self.bot._settings_cache[self.id] = g
        else:
            raise ValueError("No reason to update cache.")

    async def set(self, key, value, *, table="guild_settings"):
        z = await self.bot.db.execute(f"UPDATE {table} SET {key} = $1 WHERE guild_id = $2", value, self.id)
        await self.update_cache()
        return z

    async def set_security(self, key, value, *, base=None, table="guild_settings"):
        sec = self.security
        if base:
            try:
                sec[base][key] = value
            except KeyError:
                return False
        else:
            try:
                sec[key] = value
            except KeyError:
                return False
        await self.bot.db.execute(f"UPDATE {table} SET security = $1 WHERE guild_id = $2", json.dumps(sec), self.id)
        await self.update_cache()
        return True

    async def set_stars(self, key, value, *, table="guild_settings"):
        sec = self.stars

        try:
            sec[key] = value
        except KeyError:
            return False

        await self.bot.db.execute(f"UPDATE {table} SET stars = $1 WHERE guild_id = $2", json.dumps(sec), self.id)
        await self.update_cache()
        return True

