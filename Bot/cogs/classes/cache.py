import traceback
from sqlite3 import OperationalError

import aiosqlite


class Database:
    db = None
    need_to_create_tables = True

    @staticmethod
    def dict_factory(cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    @classmethod
    async def connect_pool(cls):
        db = await aiosqlite.connect('cache.sqlite', timeout=5)
        # db.row_factory = self.dict_factory
        cls.db = db

        if cls.need_to_create_tables:
            await cls.create_tables(db)
            cls.need_to_create_tables = False

        return db

    @staticmethod
    async def create_tables(db):
        create_table_request_list = [
            "CREATE TABLE IF NOT EXISTS streams_saver (guild_id BIGINT, streams_id text DEFAULT '')",
        ]
        for create_table_request in create_table_request_list:
            try:
                await db.execute(create_table_request)
            except OperationalError:
                pass
            else:
                await db.commit()


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
        if hasattr(guild, 'id'):
            z = guild.id
        else:
            z = guild
        super().set(z, {"guild": guild, "database": database_fetch})

    def update(self, guild, key, value):
        super().update(guild.id, key, value)


class PrefixesCache(CacheService):
    data = {}

    def set(self, guild, prefix):
        super().set(guild.id, {"prefix": prefix})


class OnlineStreamsSaver(CacheService):
    cursor = None

    async def connect(self):
        self.cursor = await Database.connect_pool()

    async def set(self, guild_id, items: dict):
        if not self.cursor:
            await self.connect()

        key = list(items.keys())[0]
        val = list(items.values())[0]

        fetch = await self._get(guild_id)
        z = fetch[1].split(',')
        z.append(str(val[0]))

        streamers = ','.join(z)

        await self.cursor.execute(
            f"UPDATE streams_saver SET {key} = '{streamers}' WHERE guild_id = {guild_id}")
        await self.cursor.commit()

    async def add(self, guild_id, stream_id):
        if not self.cursor:
            await self.connect()

        if await self.check(stream_id, guild_id) is False:
            await self.set(guild_id, {"streams_id": [stream_id]})
        else:
            fetch = await self.cursor.execute(f"SELECT * FROM streams_saver WHERE guild_id = {guild_id}")
            fetch = await fetch.fetchone()
            fetch[1].append(stream_id)

            await self.set(guild_id, {'streams_id': fetch[1]})

    async def remove(self, guild_id, stream_id):
        """called when stream goes offline"""
        if not self.cursor:
            await self.connect()

        fetch = await self._get(guild_id)
        if not fetch:
            await self.cursor.execute(f"INSERT INTO streams_saver (guild_id) VALUES ({guild_id})")
            await self.cursor.commit()
            fetch = await self._get(guild_id)

        z = fetch[1].split(',')
        if stream_id not in z:
            return
        print(z)
        z.remove(stream_id)
        print(z)

        await self.cursor.execute(
            f"UPDATE streams_saver SET streams_id = '{','.join(z)}' WHERE guild_id = {guild_id}")
        await self.cursor.commit()

    async def _get(self, guild_id):
        if not self.cursor:
            await self.connect()

        fetch = await self.cursor.execute(f"SELECT * FROM streams_saver WHERE guild_id = {guild_id}")
        fetch = await fetch.fetchone()
        return fetch

    async def check(self, streamer, guild_id, ins=True):
        # sprawdza czy stream jest w bazie

        if not self.cursor:
            await self.connect()

        fetch = await self._get(guild_id)

        if not fetch and ins:
            await self.cursor.execute(f"INSERT INTO streams_saver (guild_id) VALUES ({guild_id})")
            await self.cursor.commit()

        fetch = await self._get(guild_id)
        list_ = fetch[1].split(',')

        if str(streamer) not in list_:
            # list_.append(str(streamer))
            # streamers = ','.join(list_)
            return False

        elif str(streamer) in list_:
            return True

