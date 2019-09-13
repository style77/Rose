import json
import os
import pickle

import psycopg2
import psycopg2.extras
import redis

from flask import session, render_template, request, redirect, abort
from requests_oauthlib import OAuth2Session

from Web.classes.handler import ErrorsHandler
from Web.models import User, Client, Server
from Web.utils import checks
from Web.utils import get

scopes = ['identify', 'email', 'guilds']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


class CacheService(object):
    def __init__(self):
        self.r = redis.Redis(host='localhost', port=6379, db=0)

    def set(self, token, servers):
        self.r.set(token['access_token'], pickle.dumps({'servers': servers}))

    def check(self, token) -> bool:
        return bool(self.r.get(token['access_token']))

    def get(self, token):
        if self.check(token):
            return pickle.loads(self.r.get(token['access_token']))['servers']
        return None


class Discord:

    @classmethod
    def get_login_url(cls):
        """Make session and return login_url"""
        oauth = OAuth2Session(get('client_id'), redirect_uri=get('redirect_url'), scope=scopes)
        login_url, state = oauth.authorization_url('https://discordapp.com/api/oauth2/authorize')
        session['state'] = state
        return login_url

    @classmethod
    def get_invite(cls, *, perms):
        return f"https://discordapp.com/oauth2/authorize?client_id={get('client_id')}&scope=bot&permissions={perms}"


class DataBase:
    def __init__(self, config):
        self.conn = psycopg2.connect(
            dsn=f"dbname={config.dbname} user=style password={config.password} host={config.dbip} port={config.port}")
        self.cur = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    def fetch(self, query, *args, **kwargs):
        """kwarg one means that fetch will return only first row."""
        self.cur.execute(query)
        if kwargs.get('one'):
            return self.cur.fetchone()
        return self.cur.fetchall()

    def get_guild_settings(self, guild_id: int, **kwargs):
        one = kwargs.get('one') if 'one' in kwargs else False
        f = self.fetch("SELECT * FROM guild_settings WHERE guild_id = {}".format(guild_id), one=one)
        return f

    def update(self, guild_id: int, key, value):
        if not self.get_guild_settings(guild_id):
            self.insert_new(guild_id)
        self.cur.execute("UPDATE guild_settings SET {} = {} WHERE guild_id = {}".format(key, value, guild_id))
        self.conn.commit()
        return True

    def insert_new(self, guild_id):
        self.cur.execute("INSERT INTO guild_settings (guild_id) VALUES ({})".format(guild_id))
        self.conn.commit()


class App(ErrorsHandler):
    """Main flask application"""
    def __init__(self, app, *args, **kwargs):
        super().__init__(app)

        app.db = DataBase(app.app_config)
        self.app = app
        self.CLIENT_ID = get("client_id")
        self.CLIENT_SECRET = get("client_secret")
        self.CLIENT_TOKEN = get("client_token")
        self.cache = CacheService()

        @app.route('/')
        def main_page():
            session['current_page'] = '/'

            if any((i not in session) for i in ['lang', 'theme', 'logged_in']):
                session['lang'] = 'eng'
                session['theme'] = 'dark'  # todo change to light HAHAHHAH
                session['logged_in'] = False

            return render_template('index.html', get_text=self.app.get_text, session=session)

        @app.route('/login')
        def login_page():
            return redirect(Discord.get_login_url())

        @app.route('/logout')
        def logout_page():
            session['logged_in'] = False
            return redirect("/")

        @app.route('/invite')
        @app.route('/dodaj')
        def invite_page():
            perms = request.args.get('perms', default=8, type=int)
            return redirect(Discord.get_invite(perms=perms))

        @app.route('/support')
        @app.route('/pomoc')
        def support_page():
            return redirect("https://discord.gg/EZ3TsYY")

        @app.route('/callback')
        def callback():
            try:
                discord = OAuth2Session(
                    get('client_id'), redirect_uri=get('redirect_url'), state=session['state'], scope=scopes)
            except KeyError:
                return redirect("/")
            token = discord.fetch_token(
                "https://discordapp.com/api/oauth2/token",
                client_secret=get("client_secret"),
                authorization_response=request.url,
            )
            session['discord_token'] = token

            session['logged_in'] = True
            return redirect('/dashboard')

        @app.route('/dashboard')
        @app.route('/panel')
        @checks.user_logged
        def dashboard():
            session['current_page'] = 'dashboard'

            client = Client(client_token=get("client_token"), client_id=get("client_id"),
                            client_secret=get("client_secret"))
            user = client.get_user()

            ch = self.cache.check(session['discord_token'])
            if not ch:
                x = []
                for g in user.managed_guilds:
                    if not g['icon']:
                        g['icon'] = f"https://dummyimage.com/64/23272a/FFFFFF/&text={self.get_acronym(g['name'])}"
                    x.append(g)
                self.cache.set(session['discord_token'], x)
            else:
                x = self.cache.get(session['discord_token'])

            return render_template('server_menu.html', get_text=self.app.get_text, session=session, user=user,
                                   client=client, get_server_icon=self.get_server_icon, managed_servers=x)

        @app.route('/dashboard/<int:guild_id>')
        @app.route('/panel/<int:guild_id>')
        @checks.user_logged
        def guild(guild_id):

            session['current_page'] = f'dashboard/{guild_id}'

            client = Client(client_token=get("client_token"), client_id=get("client_id"),
                            client_secret=get("client_secret"))
            user = client.get_user()

            if guild_id not in [int(g['id']) for g in user.managed_guilds]:
                abort(403)

            db = self.app.db.get_guild_settings(guild_id)

            return render_template('settings.html', get_text=self.app.get_text, session=session, user=user,
                                   client=client, get_server_icon=self.get_server_icon, get_acronym=self.get_acronym,
                                   db=db[0], guild_id=guild_id)

        @app.route("/selector", methods=['POST', 'GET'])
        def selector():  # todo make this shit better
            if request.method == 'POST':
                result = request.form.to_dict()
                if 'theme' in result:
                    session['theme'] = result['theme']
                elif 'lang' in result:
                    session['lang'] = result['lang']
                else:
                    print(result)
                return redirect(session['current_page'])
            else:
                abort(403)

        @app.route("/update", methods=['POST', 'GET'])
        def updater():
            if request.method == 'POST':

                all_plugins = ['Music', 'RR', 'Nsfw', 'Mod']

                result = request.form.to_dict()
                settings = app.db.get_guild_settings(result['guild_id'], one=True)

                for p in all_plugins:
                    if p not in result:
                        settings['plugins_off'].append(p)
                    elif p in result and p in settings['plugins_off']:
                        settings['plugins_off'].remove(p)

                app.db.update(result['guild_id'], 'prefix', f"'{result['prefix']}'")

                p_off = self._list_to_psycopg_array(settings['plugins_off'])

                app.db.update(result['guild_id'], 'plugins_off', f"'{p_off}'")
                return redirect(session['current_page'])
            else:
                abort(403)

    @staticmethod
    def get_acronym(guild_name):
        name = guild_name.split()
        x = []
        for word in name:
            x.append(word[0])
        new_name = ''.join(x)
        return new_name

    @staticmethod
    def get_server_icon(guild):
        if guild['icon'].startswith("https://dummyimage.com/"):
            return guild['icon']
        icon_base_url = "https://cdn.discordapp.com/icons/"
        return f"{icon_base_url}{guild['id']}/{guild['icon']}.jpg"

    @staticmethod
    def get_text(text):
        try:
            lang = session['lang']
        except KeyError:
            lang = 'pl'

        with open(r'lang/{}.json'.format(lang), encoding="utf-8") as file:
            f = json.load(file)

        try:
            return f[text]
        except KeyError:
            return text

    @staticmethod
    def _list_to_psycopg_array(_list):
        return '{' + ','.join(_list) + '}'
