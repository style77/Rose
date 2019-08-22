import json
import os

from flask import session, render_template, request, redirect, abort
from requests_oauthlib import OAuth2Session
from yaml import load, Loader

from Web.classes.handler import ErrorsHandler
from Web.models import User, Client, Server
from Web.utils import checks
from Web.utils import get

scopes = ['identify', 'email', 'guilds']
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class CacheService(object):  # todo cache custom guilds avatars 2
    data = {}

    def set(self, token, servers):
        token = token['access_token']
        self.data[token] = {}
        self.data[token]['servers'] = {}
        self.data[token]['servers'] = servers

    def check(self, token):
        if token['access_token'] in self.data:
            return True
        return False

    def get(self, token):
        if token['access_token'] in self.data:
            return self.data[token['access_token']]['servers']
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


class App(ErrorsHandler):
    """Main flask application"""
    def __init__(self, app, *args, **kwargs):
        super().__init__(app)
        self.app = app
        self.CLIENT_ID = get("client_id")
        self.CLIENT_SECRET = get("client_secret")
        self.CLIENT_TOKEN = get("client_token")
        self.cache = CacheService()

        @app.route('/')
        def main_page():
            session['current_page'] = '/'
            if 'lang' not in session or 'theme' not in session or 'logged_in' not in session:
                session['lang'] = 'eng'
                session['theme'] = 'dark' # todo change to light HAHAHHAH
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
                x = [g for g in user.managed_guilds]
                self.cache.set(session['discord_token'], x)
            else:
                x = self.cache.get(session['discord_token'])

            return render_template('server_menu.html', get_text=self.app.get_text, session=session, user=user,
                                   client=client, get_server_icon=self.get_server_icon, get_acronym=self.get_acronym,
                                   managed_servers=x)

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

            db = {
                'plugins_off': ['music']
            }

            return render_template('settings.html', get_text=self.app.get_text, session=session, user=user,
                                   client=client, get_server_icon=self.get_server_icon, get_acronym=self.get_acronym,
                                   db=db)

        @app.route("/selector", methods=['POST', 'GET'])
        def selector():
            if request.method == 'POST':
                result = request.form.to_dict()
                print(result)
                try:
                    session['theme'] = result['theme']
                except KeyError:
                    try:
                        session['lang'] = result['lang']
                    except Exception as e:
                        print(e)
                print(session)
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