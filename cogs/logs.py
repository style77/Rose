from cogs.classes.plugin import Plugin


class Logs(Plugin):
    def __init__(self, bot):
        self.bot = bot


def setup(bot):
    bot.add_cog(Logs(bot))
