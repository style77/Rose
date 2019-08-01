class CacheService(object):
    def __init__(self):
        self.data = {}


class GuildSettingsCache(CacheService):

    def set(self, guild, database_fetch):
        try:
            self.__getitem__(guild.id)
        except KeyError:
            self.data[guild.id] = {}
            self.data[guild.id]["guild"] = guild
            self.data[guild.id]["database"] = database_fetch

    def __getitem__(self, guild_id):
        try:
            return self.data[guild_id]
        except KeyError:
            return None
