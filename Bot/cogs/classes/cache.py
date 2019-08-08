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
        if first not in self.data:
            self.set(first, {key: value})
        else:
            self.data[first][key] = value


class GuildSettingsCache(CacheService):
    data = {}

    def set(self, guild, database_fetch):
        super().set(guild.id, {"guild": guild, "database": database_fetch})

    def update(self, guild, key, value):
        super().update(guild.id, key, value)


class PrefixesCache(CacheService):
    data = {}

    def set(self, guild, prefix):
        super().set(guild.id, {"prefix": prefix})


class OnlineStreamsSaver(CacheService):
    data = {}

    def set(self, first, items: dict):
        self.data[first] = items

    def add(self, guild_id, stream_id):
        if guild_id not in self.data:
            self.set(guild_id, {"streams_id": [stream_id]})
        else:
            self.data[guild_id]['streams_id'].append(stream_id)

    def remove(self, guild_id, stream_id):
        """called when stream goes offline"""
        if guild_id in self.data:
            self.data[guild_id].pop("stream_id")

