from functools import wraps
from flask import session, redirect
from werkzeug.exceptions import Aborter

abort = Aborter()

def user_logged(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session or 'logged_in' not in session:
            # return redirect('/') # todo
            abort(403)
        return func(*args, **kwargs)
    return wrapper
