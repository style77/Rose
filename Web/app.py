# SIEMA KURWA NIENAWIDZE MYSELF
import json

def get(thing):
    with open(r"config.json") as json_file:
        f = json.load(json_file)
    return f[thing]

CLIENT_ID =
CLIENT_SECRET =