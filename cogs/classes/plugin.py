from discord.ext import commands


class PluginException(commands.CommandError):
    pass


class Plugin(commands.Cog):

    @property
    def name(self):
        return self.qualified_name

    def get_all_commands(self):

        commands_ = []

        for command in self.walk_commands():
            commands_.append(command)

        return commands_

    async def turn_off(self, db, guild_id):
        plugins = await db.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", guild_id)
        if self.name in plugins[0]:
            raise PluginException("Ten plugin jest już wyłączony.")
        plugins[0].append(self.name)
        await db.execute("UPDATE guild_settings SET plugins_off = $1 WHERE guild_id = $2", plugins[0], guild_id)

    async def turn_on(self, db, guild_id):
        plugins = await db.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", guild_id)
        if self.name in plugins[0]:
            raise PluginException("Ten plugin jest już włączony.")
        plugins[0].remove(self.name)
        await db.execute("UPDATE guild_settings SET plugins_off = $1 WHERE guild_id = $2", plugins[0], guild_id)