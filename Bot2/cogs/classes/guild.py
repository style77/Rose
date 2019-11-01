from ..utils.misc import get_prefix
from ..utils.DEFAULTS import HEARTBOARD_EMOJI, STARS_COUNT, WARNS_KICK


class Guild(object):
    """Base class for Rose's Guild representation."""
    def __init__(self, bot, req):
        self.data = req
        self.bot = bot

        self.guild_obj = bot.get_guild(req['guild_id'])
        self.id = req['guild_id']

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
    def heartboard_emoji(self):  # todo update when heartboards will have custom emojis
        return HEARTBOARD_EMOJI

    @property
    def stars_count(self):
        return self.data['stars_count'] or STARS_COUNT

    @property
    def warns_kick(self):
        return self.data['warns_kick'] or WARNS_KICK

    @property
    def emoji_censor(self):
        return self.data['emoji_censor'] or False

    @property
    def anti_raid(self):
        return self.data['anti_raid'] or False

    @property
    def anti_link(self):
        return self.data['anti_link'] or False

    @property
    def levels(self):
        return self.data['levels'] or False

    @property
    def boost(self):
        return self.data['boost'] or False

    def get_starboard(self):
        return self.bot.get_channel(self.data['starboard']) or None

    def get_auto_role(self):
        return self.guild_obj.get_role(self.data['auto_role']) or None

    def get_mute_role(self):
        return self.guild_obj.get_role(self.data['mute_role']) or None

    async def set(self, key, value, *, table="guild_settings"):
        await self.bot.db.execute(f"UPDATE {table} SET {key} = $1 WHERE guild_id = $2", value, self.id)
        return True
