from flask import session
from requests_oauthlib import OAuth2Session

from Web.models import http
from Web.utils import get

class User(object):
    def __init__(self, user, **kwargs):
        self.user = user
        self.client_token = get("client_token")
        self.base_api_link = 'https://discordapp.com/api/v6'

    def __getattr__(self, attr):
        try:
            return self.user[attr]
        except KeyError:
            return None

    def get_user_managed_servers(self, guilds):
        return list(
            filter(
                lambda g: (g['owner'] is True) or
                          bool((int(g['permissions']) >> 5) & 1),
                guilds)
        )

    @property
    def managed_guilds(self):
        g = self.guilds
        user_guilds = self.get_user_managed_servers(g)
        return user_guilds

    @property
    def guilds(self):
        discord = OAuth2Session(get("client_id"), token=session['discord_token'])
        r = discord.get(self.base_api_link + '/users/@me/guilds')
        return r.json()