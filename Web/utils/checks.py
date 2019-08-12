from functools import wraps
from flask import abort, session


def user_logged(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session['logged_in']:
            abort(401)
        return func(*args, **kwargs)
    return wrapper
