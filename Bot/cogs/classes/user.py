import json


class User:
    def __init__(self, bot, req):
        self.bot = bot
        self._req = req

    @property
    def _raw(self):
        return self._req

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
    def settings(self):
        return json.loads(self.data['user_settings'])

    @property
    def tinder(self):
        return json.loads(self.data['tinder'])

    @property
    def id(self):
        return self.data['id']

    @property
    def level(self):
        return self.data['level']

    @property
    def exp(self):
        return self.data['exp']

    @property
    def last_vote(self):
        return self.data['last_vote']

    @property
    def reputation(self):
        return json.loads(self.data['reputation'])

    async def set(self, key, value, *, table="users"):
        query = f"UPDATE {table} SET {key} = $1 WHERE id = $2"

        await self.bot.db.execute(query, value, self.id)
