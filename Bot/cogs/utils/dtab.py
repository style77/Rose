import asyncpg
from . import utils

class Db():

    @staticmethod
    async def fetch(query, *args):
        pg_con = await asyncpg.create_pool(dsn=f"postgresql://{utils.Utils.get_from_config('dbip')}/{utils.Utils.get_from_config('dbname')}", user="style", password=utils.Utils.get_from_config("password"))
        r = await pg_con.fetch(query, *args)
        if not r:
            return None
        return r[0]

    @staticmethod
    async def execute(query, *args):
        pg_con = await asyncpg.create_pool(dsn=f"postgresql://{utils.Utils.get_from_config('dbip')}/{utils.Utils.get_from_config('dbname')}", user="style", password=utils.Utils.get_from_config("password"))
        r = await pg_con.execute(query, *args)
        if not r:
            return None
        return r[0]
