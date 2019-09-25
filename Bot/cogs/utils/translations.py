import builtins
import json


def translate(lang, text):
    if lang not in ["ENG"]:
        return text
    with open(r"cogs/utils/translation_files/{}.json".format(lang), encoding="utf8", errors='ignore') as file_:
        z = json.load(file_)
        try:
            return z[text]
        except KeyError:
            print(f"Nie znaleziono {text} w pliku {file_}")
            return text


async def language(bot, guild_id):
    guild = bot.get_guild(guild_id)
    if not guild:
        return "ENG"
    z = await bot.pg_con.fetch("SELECT lang FROM guild_settings WHERE guild_id = $1", guild.id)
    if z:
        lang = z[0]['lang']
    else:
        lang = "ENG"
    return lang


builtins._ = translate
builtins.get_language = language
