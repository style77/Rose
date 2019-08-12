class Server(object):
    def __init__(self, server):
        self.server = server

    def __getattr__(self, attr):
        try:
            return self.server[attr]
        except KeyError:
            return None
