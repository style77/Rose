from discord.ext import commands


class Plugin(commands.Cog):
    def __init__(self, bot, *, command_attrs=None):
        if command_attrs is None:
            command_attrs = dict()
        self.bot = bot

        self.command_attrs = command_attrs

    def is_turnable(self):
        return not self.command_attrs['not_turnable']

    @property
    def name(self):
        return self.qualified_name

    def get_all_commands(self):

        commands_ = []

        for command in self.walk_commands():
            commands_.append(command)

        return commands_

    async def set_plugin(self, db, guild_id, on=True):
        if not self.is_turnable():
            raise commands.BadArgument(f"{self.qualified_name} is not possible to turn off/on")

        plugins = await db.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", guild_id)
        if on is False:
            if self.name in plugins[0]:
                raise commands.BadArgument("This plugin is already on.")
            plugins[0].append(self.name)
        else:
            if self.name not in plugins[0]:
                raise commands.BadArgument("This plugin is already off.")
            plugins[0].remove(self.name)
        await db.execute("UPDATE guild_settings SET plugins_off = $1 WHERE guild_id = $2", plugins[0], guild_id)

    async def turn_off(self, db, guild_id):
        await self.set_plugin(db, guild_id, False)

    async def turn_on(self, db, guild_id):
        await self.set_plugin(db, guild_id)