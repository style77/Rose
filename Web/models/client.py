from utils import get
from . import http, User

class Client(object):
    def __init__(self, **kwargs):
        self.client_token = kwargs.get("client_token") or None
        self.client_id = kwargs.get("client_id") or None
        self.client_secret = kwargs.get("client_secret") or None
        self.base_api_link = 'https://discordapp.com/api/v6'

    @property
    def guilds(self):
        headers = {'Authorization': f'Bot {self.client_token}'}
        return http.get(f'{self.base_api_link}/users/@me/guilds', headers=headers)

    @property
    def guilds_ids(self):
        return [str(g['id']) for g in self.guilds]

    @staticmethod
    def get_user_managed_servers(guilds):
        return list(
            filter(
                lambda g: (g['owner'] is True) or
                          bool((int(g['permissions']) >> 5) & 1),
                guilds)
        )

    def get_user(self, user_id=None):
        if not self.client_token:
            return None

        user_id = user_id or '@me'

        user = http.get(f"{self.base_api_link}/users/{user_id}",
                        headers={'Authorization': f'Bot {self.client_token}'})

        return User(user, client_token=get("client_token"))

    def get_server(self, server_id):
        if not self.client_token:
            return None

        return http.get(
            f"{self.base_api_link}/guilds/{server_id}",
            headers={'Authorization': f'Bot {self.client_token}'},
        )
