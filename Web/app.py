import json
import secrets

from flask import Flask

# from . import models
from Web.classes.handler import ErrorsHandler
from Web.classes.main import App

app = Flask("Rose")
app.secret_key = secrets.token_urlsafe(16)
app.eh = ErrorsHandler(app)

app.main = App(app)

app.get_text = app.main.get_text

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
