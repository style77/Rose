from flask import render_template
from jinja2 import TemplateNotFound

class ErrorsHandler:
    def __init__(self, app):
        self.app = app

        # @self.app.errorhandler(401)
        # def unauthorized(e):
        #     return 'Unauthorized', 401

        # @self.app.errorhandler(403)
        # def forbidden(e):
        #     return 'Forbidden', 403

        # @self.app.errorhandler(404)
        # def not_found(e):
        #     return render_template(r'errors/404.html', get_text=self.app.get_text), 404

        # @self.app.errorhandler(500)
        # def internal_server_error(e):
        #     return 'Internal server error', 500

        # @self.app.errorhandler(TemplateNotFound)
        # def oops_error(e):
        #     """lol dont ask me anything about that im just lazy ok?"""
        #     return f"<a>{self.app.get_text('NotFound')}</a>"

