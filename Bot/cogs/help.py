import discord
from discord.ext import commands

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = NewHelpCommand()
        bot.help_command.cog = self
        self.bot.get_command("help").hidden = True

    def cog_unload(self):
        self.bot.help_command = self._original_help_command

def setup(bot):
    bot.add_cog(Help(bot))

class NewHelpCommand(commands.HelpCommand):
    def __init__(self):
        super().__init__()
        self.zws = '\u200b'

    async def get_blocked_commands(self, guild_id):
        f = await self.context.bot.pg_con.fetch("SELECT blocked_commands FROM guild_settings WHERE guild_id = $1",
                                                guild_id)

        plugins_off = await self.context.bot.pg_con.fetch("SELECT plugins_off FROM guild_settings WHERE guild_id = $1",
                                                          guild_id)

        blocked_commands = []
        blocked_commands.append(f[0])
        #
        # if len(plugins_off[0]) > 0:
        #     for plugin in plugins_off[0]:
        #         cog = self.context.bot.get_cog(plugin)
        #         blocked_commands.append([command.name for command in cog.commands])

        return blocked_commands

    async def send_command_help(self, command):
        if command.name in await self.get_blocked_commands(self.context.guild.id):
            return await self.context.send(_(self.context.lang, "Ta komenda jest zablokowana."))
        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=command.name,
                     icon_url=self.context.bot.user.avatar_url)
        params = []
        for param in command.clean_params:
            params.append(f"[{param}]")
        e.add_field(name=_(self.context.lang, "Użycie"), value='`' + f"{command.name} {' '.join(params)}" + '`',
                    inline=False)
        try:
            e.add_field(name=_(self.context.lang, "Twoje wymagane uprawnienia"),
                        value='`' + ', '.join(command.callback.required_permissions) + '`', inline=False)
        except AttributeError:
            pass
        if command.aliases:
            e.add_field(name=_(self.context.lang, "Aliasy"), value='`' + ', '.join(command.aliases) + '`', inline=False)
        # e.add_field(name=_(self.context.lang, "Wymagane uprawnienia bota"), value=f"{command.name} {' '.join(params)}")
        if command.help is not None:
            e.set_footer(text=_(self.context.lang, command.help))

        await self.context.send(embed=e)

    async def send_group_help(self, group):
        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=group.qualified_name,
                     icon_url=self.context.bot.user.avatar_url)
        for command in group.commands:
            params = []
            for param in command.clean_params:
                params.append(f"[{param}]")
            params = ' '.join(params)
            cmd_name = f"{command.name} {params if command.clean_params else ''}"
            cmd_desc = _(self.context.lang,
                         command.help if command.help is not None else 'Brak opisu.')
            if command.name in await self.get_blocked_commands(self.context.guild.id):
                cmd_name = "~~" + cmd_name + "~~"
                cmd_desc = "~~" + cmd_desc + "~~"

            e.add_field(name=cmd_name, value=cmd_desc, inline=False)

        await self.context.send(embed=e)

    async def send_cog_help(self, cog):
        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=cog.qualified_name,
                     icon_url=self.context.bot.user.avatar_url)

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        if filtered:
            for command in cog.get_commands():

                params = []
                for param in command.clean_params:
                    params.append(f"[{param}]")
                params = ' '.join(params)

                cmd_name = f"{command.name} {params if command.clean_params else ''}"
                cmd_desc = _(self.context.lang,
                             command.help if command.help is not None else 'Brak opisu.')

                if self.context.guild is not None:
                    if command.name in await self.get_blocked_commands(self.context.guild.id):
                        cmd_name = "~~" + cmd_name + "~~"
                        cmd_desc = "~~" + cmd_desc + "~~"

                e.add_field(
                    name=cmd_name, value=cmd_desc, inline=False)

                if isinstance(command, commands.Group):
                    for cmd in command.commands:
                        params = []
                        for param in cmd.clean_params:
                            params.append(f"[{param}]")
                        params = ' '.join(params)

                        cmd_name = f"{command.name} {cmd.name} {params if cmd.clean_params else ''}"
                        cmd_desc = _(self.context.lang,
                                     cmd.help if cmd.help is not None else 'Brak opisu.')

                        if self.context.guild is not None:
                            if cmd.name in await self.get_blocked_commands(self.context.guild.id):
                                cmd_name = "~~" + cmd_name + "~~"
                                cmd_desc = "~~" + cmd_desc + "~~"

                        e.add_field(
                            name=cmd_name, value=cmd_desc, inline=False)

        if cog.description is not None:
            e.set_footer(text=_(self.context.lang, cog.description))
        await self.context.send(embed=e)

    async def send_bot_help(self, mapping):
        lines = []
        e = discord.Embed(color=self.context.bot.color)
        for cog, cog_commands in mapping.items():
            filtered = await self.filter_commands(cog_commands, sort=True)

            if filtered:
                try:
                    cog_name = f"{cog.qualified_name}\n"
                except AttributeError:
                    pass
                for command in filtered:
                    if command.name in lines:
                        return
                    lines.append('`' + command.name + '`')
                    if isinstance(command, commands.Group):
                        for cmd in command.commands:
                            if f"`{command.name} {cmd.name}`" in lines:
                                return
                            lines.append(f"`{command.name} {cmd.name}`")
                            # if isinstance(cmd, commands.Group):
                            # for cmd2 in command.commands:
                            # if f"{command.name} {cmd.name} {cmd2.name}" in lines:
                            # return
                            # lines.append(f"{command.name} {cmd.name} {cmd2.name}")
            if len(lines) > 0:
                e.add_field(name=cog_name, value=', '.join(lines), inline=False)
                lines.clear()

        e.set_author(name=f"{self.context.bot.user.name} help", icon_url=self.context.bot.user.avatar_url)
        e.set_footer(text=
                     "🌹 " + _(self.context.lang,
                               "{} komend razem. Bot stworzony przez Style. Dołącz do serwera pomocy z botem w razie problemów użyj: {}support. {}help [cmd_or_ext] - aby dowiedzieć się więcej o komendzie lub module.").format(
                         len(self.context.bot.commands), self.clean_prefix, self.clean_prefix))
        await self.context.send(embed=e)
