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

    async def _get_blocked_commands(self, guild_id):
        plugins_off = await self.context.bot.db.fetchrow("SELECT blocked_cogs FROM guild_settings WHERE guild_id = $1",
                                                         guild_id)
        commands_off = await self.context.bot.db.fetchrow("SELECT blocked_commands FROM guild_settings WHERE guild_id "
                                                          "= $1",
                                                          guild_id)

        blocked_commands = []
        blocked_commands.extend(commands_off)

        if plugins_off:
            for plugin in plugins_off[0]:
                cog = self.context.bot.get_cog(plugin)
                if not cog:
                    continue
                blocked_commands.extend(command.name for command in cog.commands)

        return blocked_commands

    async def send_command_help(self, command):
        if command.name in await self._get_blocked_commands(self.context.guild.id):
            return await self.context.send(self.context.lang['command_locked'])

        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=command.name, icon_url=self.context.bot.user.avatar_url)

        params = []

        for param in command.clean_params:
            params.append(f"[{param}]")

        e.add_field(name=self.context.lang['usage'], value=f"`{command.name} {' '.join(params)}`",
                    inline=False)
        try:
            e.add_field(name=self.context.lang['you_need_permissions'],
                        value=f"`{', '.join(command.callback.required_permissions)}`", inline=False)
        except AttributeError:
            pass

        if command.aliases:
            e.add_field(name="Aliases", value=f"`{', '.join(command.aliases)}`", inline=False)

        #e.add_field(name=_(self.context.lang, "Wymagane uprawnienia bota"), value=f"{command.name} {' '.join(params)}")

        try:
            e.set_footer(text=self.context.lang[f'{command.name}_doc'])
        except KeyError:
            pass

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

            try:
                cmd_desc = self.context.lang[f"{group.name}_doc"]
            except KeyError:
                cmd_desc = self.context.lang['empty_desc']

            if command.name in await self._get_blocked_commands(self.context.guild.id):
                continue

            e.add_field(name=cmd_name, value=cmd_desc, inline=False)

        try:
            e.set_footer(text=self.context.lang[f"{group.name}_doc"])
        except KeyError:
            pass

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

                try:
                    cmd_desc = self.context.lang[f"{command.name}_doc"]
                except KeyError:
                    cmd_desc = self.context.lang['empty_desc']

                if self.context.guild is not None:
                    if command.name in await self._get_blocked_commands(self.context.guild.id):
                        continue

                e.add_field(
                    name=cmd_name, value=cmd_desc, inline=False)

                if isinstance(command, commands.Group):
                    for cmd in command.commands:
                        params = []

                        for param in cmd.clean_params:
                            params.append(f"[{param}]")

                        params = ' '.join(params)

                        cmd_name = f"{command.name} {cmd.name} {params if cmd.clean_params else ''}"

                        try:
                            cmd_desc = self.context.lang[f"{cmd.name}_doc"]
                        except KeyError:
                            cmd_desc = self.context.lang['empty_desc']

                        if self.context.guild is not None:
                            if cmd.name in await self._get_blocked_commands(self.context.guild.id):
                                continue

                        e.add_field(
                            name=cmd_name, value=cmd_desc, inline=False)

        try:
            e.set_footer(text=self.context.lang[f"{cog.name}_doc"])
        except KeyError:
            pass

        await self.context.send(embed=e)

    async def send_bot_help(self, mapping):
        lines = []
        e = discord.Embed(color=self.context.bot.color)
        for cog, cog_commands in mapping.items():
            if not cog:
                continue
            cog_name = f"{cog.qualified_name}\n"
            filtered = await self.filter_commands(cog_commands, sort=True)

            if filtered:
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
        e.set_footer(text="\U0001f339" + self.context.lang['bot_description'].format(
            len(self.context.bot.commands), self.clean_prefix, self.clean_prefix))
        await self.context.send(embed=e)
