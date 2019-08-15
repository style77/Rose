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


class Discord:

    @staticmethod
    def get_login_url():
        """Make session and return login_url"""
        oauth = OAuth2Session(get('client_id'), redirect_uri=get('redirect_url'), scope=scopes)
        login_url, state = oauth.authorization_url('https://discordapp.com/api/oauth2/authorize')
        session['state'] = state
        return login_url


class App(ErrorsHandler):
    """Main flask application"""
    def __init__(self, app, *args, **kwargs):
        super().__init__(app)
        self.app = app
        self.CLIENT_ID = get("client_id")
        self.CLIENT_SECRET = get("client_secret")
        self.CLIENT_TOKEN = get("client_token")

        @app.route('/')
        def main_page():
            session['current_page'] = '/'
            if not session:
                session['lang'] = 'pl'
                session['theme'] = 'dark'
                session['logged_in'] = False

            return render_template('index.html', get_text=self.app.get_text, session=session)

        @app.route('/login')
        def login_page():
            return redirect(Discord().get_login_url())

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
        @checks.user_logged
        def dashboard():
            session['current_page'] = 'dashboard'

            client = Client(client_token=get("client_token"), client_id=get("client_id"),
                            client_secret=get("client_secret"))
            user = client.get_user()
            return render_template('dashboard.html', get_text=self.app.get_text, session=session, user=user,
                                   client=client, get_server_icon=self.get_server_icon, get_acronym=self.get_acronym)

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