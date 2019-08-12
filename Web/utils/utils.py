from yaml import load, Loader

def get(thing):
    with open(r"config.yml") as json_file:
        f = load(json_file, Loader=Loader)
    return f[thing]