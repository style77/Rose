from discord.utils import escape_markdown, escape_mentions


def clean_text(text):
    z = escape_markdown(text)
    z = escape_mentions(z)
    return z
