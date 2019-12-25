import traceback
import secrets
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from .classes.other import Plugin


class ErrorHandler(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        lang = ctx.lang

        if hasattr(ctx.command, 'on_error'):
            return

        ignored = (commands.CommandNotFound)
        error = getattr(error, 'original', error)

        if isinstance(error, ignored):
            return

        elif isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, discord.Forbidden):
            try:
                await ctx.send(lang["no_bot_permissions"])
            except discord.HTTPException:
                pass
            return await ctx.add_react(False)

        elif isinstance(error, commands.NSFWChannelRequired):
            await ctx.send(ctx.lang['channel_is_not_nsfw'])
            return await ctx.add_react(False)

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(f"{lang['no_permissions']} `{', '.join(error.missing_perms)}`")
            return await ctx.add_react(False)

        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(f"{lang['no_bot_permissions']} ({ctx.command.qualified_name}) {lang['to_use_cmd']} **{', '.join(error.missing_perms)}**")
            return await ctx.add_react(False)

        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(f"{lang['command']} {ctx.command.qualified_name} {lang['cmd_off']}.")
            return await ctx.add_react(False)

        elif isinstance(error, commands.NotOwner):
            await ctx.send(lang['need_to_be_owner'])
            return await ctx.add_react(False)

        elif isinstance(error, commands.CommandOnCooldown):
            seconds = error.retry_after
            seconds = round(seconds, 2)
            hours, remainder = divmod(int(seconds), 3600)
            minutes, seconds = divmod(remainder, 60)

            time = timedelta(hours=hours, minutes=minutes, seconds=seconds)

            await ctx.send(f"Poczekaj jeszcze {time}.")
            return await ctx.add_react(False)

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.author.send(f"**{ctx.command.qualified_name}** {lang['cant_use_in_pms']}.") # i dont have idea how to make it so lemme use eng as default language
            except:
                pass
            return await ctx.add_react(False)

        elif isinstance(error, commands.CheckFailure):
            await ctx.send(lang['no_permissions'] + '.')
            return await ctx.add_react(False)

        elif isinstance(error, (commands.BadArgument, )):
            print(error)
            await ctx.send(str(error))
            return await ctx.add_react(False)

        elif isinstance(error, commands.UserInputError):
            await ctx.send(f"{lang['proper_use']} `{ctx.prefix}{ctx.command.qualified_name} {' '.join(list(ctx.command.clean_params))}`")
            return await ctx.add_react(False)

        else:
            stack = 8
            traceback_text = "\n".join(traceback.format_exception(
                type(error), error, error.__traceback__, stack))

            print(traceback_text)

            owner = ctx.bot.get_user(ctx.bot.owner_id)

            traceback.print_exc()

            code = secrets.token_hex(7)

            pure_fmt = f"CODE: {code} - Command: {ctx.command.qualified_name} - Guild: {ctx.guild.id} - " \
                       f"Time: {datetime.utcnow()}" \
                       f"\n{traceback_text}\n\n\n"

            await owner.send(
                f"Command: {ctx.command.qualified_name}\nGuild: {ctx.guild}\nTime: {datetime.utcnow()}"
                f"```py\n{traceback_text}```")

            fmt = f"{lang['report_problem_1']} `discord.gg/{self.bot._config['support']}`\n\t\t" \
                  f"{lang['report_problem_2']}\n\nCODE: **{code}**"

            await self.bot.loop.create_task(self.write_error(pure_fmt))

            await ctx.send(fmt)

    @staticmethod
    async def write_error(error):
        with open(r"errors.log", "a+") as f:
            f.write(error)


def setup(bot):
    bot.add_cog(ErrorHandler(bot))
