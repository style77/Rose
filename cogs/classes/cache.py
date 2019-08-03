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


class OnlineStreamsSaver(object):
    """Its psuedo cacher which is just saving streamers to list"""
    data = {}

    def set(self, first, items: dict):
        self.data[first] = items

    def add(self, guild_id, stream_id):
        if stream_id not in self.data:
            self.set(guild_id, {"stream_id": stream_id})

    def remove(self, guild_id, stream_id):
        """called when stream goes offline"""
        if guild_id in self.data:
            self.data[guild_id].pop("stream_id")

