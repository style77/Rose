import secrets

from flask import Flask

from Web import models
from Web.classes.handler import ErrorsHandler
from Web.classes.main import App, CacheService

app = Flask("Rose")

# website_url = 'rose.localhost:5000'
# app.config['SERVER_NAME'] = website_url

app.app_config = models.Config()
app.secret_key = secrets.token_urlsafe(16)
app.eh = ErrorsHandler(app)

app.main = App(app)

app.get_text = app.main.get_text

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=app.app_config.debug)
