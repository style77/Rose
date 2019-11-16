from yaml import load, Loader


class Config:
    def __init__(self):
        with open(r"config.yml", 'r') as f:
            self.file = load(f, Loader=Loader)

    def __getattr__(self, item):
        try:
            return self.file[item]
        except KeyError:
            return None
