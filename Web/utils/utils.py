from yaml import load, Loader


def get(thing):
    with open(r"config.yml") as json_file:
        f = load(json_file, Loader=Loader)
    return f[thing]


class Settings(object):
    def __init__(self, db):
        self.guild = db

    def __getattr__(self, item):
        try:
            return self.guild[item]
        except Exception as e:
            print(e)
