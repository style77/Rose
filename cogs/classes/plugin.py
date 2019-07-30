import typing

from discord.ext import commands

class PluginException(commands.CommandError):
    pass

class Plugin(commands.Cog):
    def __init__(self):
        self.commands = self.get_all_commands()

    @property
    def name(self):
        return self.qualified_name

    def get_all_commands(self):
        
        commands = []
        
        for command in self.walk_commands():
            commands.append(command)

        return commands

    async def _turn_off(self, db, guild_id):
        plugins = await db.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", guild_id)
        if self.qualified_name in plugins[0]:
            raise PluginException(_("Ten plugin jest już wyłączony")
        else:
            print(2)
