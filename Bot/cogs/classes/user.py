import json


class User:
    def __init__(self, bot, req):
        self.bot = bot
        self._req = req

    @property
    def data(self):
        return self._req

    @property
    def last_nicknames(self):
        return json.loads(self.data['last_nicknames'])

    @property
    def last_usernames(self):
        return json.loads(self.data['last_usernames'])

    @property
    def id(self):
        return self.data['id']

    async def set(self, key, value, *, table="users"):
        query = f"UPDATE {table} SET {key} = $1 WHERE id = $2"

        await self.bot.db.execute(query, value, self.id)
