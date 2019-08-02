class CacheService(object):
    data = {}

    def set(self, first, items: dict):
        self.data[first] = items

    def get(self, arg):
        try:
            return self.data[arg]
        except KeyError:
            return None

    def update(self, first, key, value):
        self.data[first][key] = value


class GuildSettingsCache(CacheService):

    def set(self, guild, database_fetch):
        super().set(guild.id, {"guild": guild, "database": database_fetch})

    def update(self, guild, key, value):
        super().update(guild.id, key, value)


class PrefixesCache(CacheService):

    def set(self, guild, prefix):
        super().set(guild.id, {"prefix": prefix})
