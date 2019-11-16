from werkzeug.exceptions import HTTPException, default_exceptions

from Web import app


class NotLogged(HTTPException):
    code = 789
    description = app.get_text('NotLogged')