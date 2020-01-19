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

    def get_text(self, text):
        translated_text = self.context.lang[text]

        print(translated_text)

        if text == translated_text:
            return None
        return translated_text

    async def _get_blocked_cogs(self):
        if not self.context.guild:
            return []

        guild = await self.context.bot.get_guild_settings(self.context.guild.id)
        plugins_off = await guild.get_blocked_cogs()

        return plugins_off

    async def _get_blocked_commands(self):
        if not self.context.guild:
            return []

        guild = await self.context.bot.get_guild_settings(self.context.guild.id)
        commands_off = await guild.get_blocked_commands()

        return commands_off

    async def send_command_help(self, command):
        if command.name in await self._get_blocked_commands():
            return await self.context.send(self.get_text('command_locked'))

        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=command.name, icon_url=self.context.bot.user.avatar_url)

        params = []

        for param in command.clean_params:
            params.append(f"[{param}]")

        e.add_field(name=self.get_text('usage'), value=f"`{command.name} {' '.join(params)}`",
                    inline=False)
        try:
            e.add_field(name=self.get_text('you_need_permissions'),
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

        params = list()
        for param in group.clean_params:
            params.append(f"[{param}]")
        params = ' '.join(params)  # i hate repeating myself

        e.set_author(name=f"{group.qualified_name} {params}",
                     icon_url=self.context.bot.user.avatar_url)

        commands_without_desc = list()

        for command in group.commands:
            if command.name in await self._get_blocked_commands():
                continue

            cmd_desc = self.get_text(f"{command.qualified_name.replace(' ', '_')}_doc")
            if not cmd_desc:
                commands_without_desc.append(command)
                continue

            params = list()
            for param in command.clean_params:
                params.append(f"[{param}]")
            params = ' '.join(params)  # i hate repeating myself

            cmd_name = f"{command.name} {params}"

            e.add_field(name=cmd_name, value=cmd_desc, inline=False)

        if commands_without_desc:
            z = []
            for command in commands_without_desc:
                params = list()
                for param in command.clean_params:
                    params.append(f"[{param}]")
                params = ' '.join(params)  # i hate repeating myself

                z.append(f"{command.name} {params}")

            x = '\n'.join(z)
            e.description = f"{self.get_text('commands_without_description')}\n`{x}`"

        group_doc = self.get_text(f'{group.qualified_name}_doc')
        if group_doc:
            e.set_footer(text=group_doc)

        await self.context.send(embed=e)

    async def send_cog_help(self, cog):
        e = discord.Embed(color=self.context.bot.color)
        e.set_author(name=cog.qualified_name,
                     icon_url=self.context.bot.user.avatar_url)

        filtered = await self.filter_commands(cog.get_commands(), sort=True)
        blocked_commands = await self._get_blocked_commands()

        commands_without_desc = list()

        if filtered:
            for command in cog.get_commands():

                print(command)

                if command.qualified_name in blocked_commands:
                    continue

                cmd_desc = self.get_text(f"{command.qualified_name.replace(' ', '_')}_doc")
                if not cmd_desc:
                    commands_without_desc.append(command)
                    continue

                params = list()
                for param in command.clean_params:
                    params.append(f"[{param}]")
                params = ' '.join(params)  # i hate repeating myself

                cmd_name = f"{command.name} {params}"

                e.add_field(name=cmd_name, value=cmd_desc, inline=False)

            if commands_without_desc:
                z = []
                for command in commands_without_desc:
                    params = list()
                    for param in command.clean_params:
                        params.append(f"[{param}]")
                    params = ' '.join(params)  # i hate repeating myself

                    z.append(f"{command.name} {params}")

                x = '\n'.join(z)
                e.description = f"{self.get_text('commands_without_description')}\n`{x}`"

            cog_doc = self.get_text(f"{cog.qualified_name}_doc")
            if cog_doc:
                e.set_footer(text=cog_doc)

        await self.context.send(embed=e)

    async def send_bot_help(self, mapping):
        lines = []
        e = discord.Embed(color=self.context.bot.color)

        blocked_cogs = await self._get_blocked_cogs()
        blocked_commands = await self._get_blocked_commands()

        for cog, cog_commands in mapping.items():
            if not cog:
                continue

            if cog.qualified_name in blocked_cogs:
                continue

            if cog.qualified_name == "NSFW":
                cog_name = "\U00002757NSFW"
            elif cog.qualified_name == "SFW":
                cog_name = "\U00002755SFW"
            else:
                cog_name = f"{cog.qualified_name}\n"

            filtered = await self.filter_commands(cog_commands, sort=True)

            if filtered:
                for command in filtered:
                    if command.name in lines:
                        return

                    if command.name in blocked_commands:
                        continue

                    lines.append('`' + command.qualified_name + '`')
                    if isinstance(command, commands.Group):
                        for cmd in command.commands:
                            if f"`{cmd.qualified_name}`" in lines:
                                return
                            lines.append(f"`{cmd.qualified_name}`")

            if len(lines) > 0:
                e.add_field(name=cog_name, value=', '.join(lines), inline=False)
                lines.clear()

        e.set_author(name=f"{self.context.bot.user.name} help", icon_url=self.context.bot.user.avatar_url)
        e.set_footer(text="\U0001f339" + self.context.lang['bot_description'].format(
            len(self.context.bot.commands), self.clean_prefix, self.clean_prefix))
        await self.context.send(embed=e)
