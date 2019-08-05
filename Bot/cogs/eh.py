import traceback
from datetime import datetime

import discord
from discord.ext import commands

from .cat import CatIsDead, MemberDoesNotHaveCat
from .classes.converters import TrueFalseError
from .mod import NewGuild
from .music import add_react
from .tags import TagAlreadyExists, TagNotFound


class MemberInBlacklist(commands.CommandError):
    pass


class CommandErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

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
                await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Bot nie posiada permisji."))
            except discord.HTTPException:
                pass
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.MissingPermissions):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Brakuje Ci uprawnień **{perms}**").format(perms=', '.join(error.missing_perms)))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Bot nie posiada permisji ({perms}) do wykonania komendy **{cmd_name}**").format(cmd_name=ctx.command.name, perms=', '.join(error.missing_perms)))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.DisabledCommand):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "{cmd_name} została wyłączona.").format(cmd_name=ctx.command.name))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.NotOwner):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Musisz być właścicielem bota, aby wykonać tą komende."))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.CommandOnCooldown):
            seconds = error.retry_after
            seconds = round(seconds, 2)
            hours, remainder = divmod(int(seconds), 3600)
            minutes, seconds = divmod(remainder, 60)

            now = datetime.utcnow()
            time = datetime(now.year, now.month, now.day, minute=minutes, second=seconds)
            time = time.strftime("%Mm:%Ss")

            await ctx.send(
                _(await get_language(self.bot, ctx.guild.id), "Poczekaj jeszcze {time}.").format(time=time))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                await ctx.author.send(_("ENG", "**{cmd_name}** nie może być użyta w prywatnych wiadomościach.").format(cmd_name=ctx.command.name)) # i dont have idea how to make it so lemme use eng as default language
            except:
                pass
            return await add_react(ctx.message, False)

        elif isinstance(error, MemberDoesNotHaveCat):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Nie masz kota."))
            return await add_react(ctx.message, False)

        elif isinstance(error, CatIsDead):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Twój kot nie żyje."))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.UserInputError):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Użycie `{prefix}{cmd_name} {args}`").format(prefix=ctx.prefix, cmd_name=ctx.command.name, args=' '.join(list(ctx.command.clean_params))))
            return await add_react(ctx.message, False)

        elif isinstance(error, TrueFalseError):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Użycie `{}set {} True/False`").format(ctx.prefix, ctx.command.name))
            return await add_react(ctx.message, False)

        elif isinstance(error, MemberInBlacklist):
            fetch = await self.bot.pg_con.fetchrow("SELECT * FROM blacklist WHERE user_id = $1", ctx.author.id)
            reason = fetch['reason']
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Nie możesz używać komend, gdyż zostałeś zablokowany. Powód `{}`").format(reason))
            return await add_react(ctx.message, False)

        elif isinstance(error, NewGuild):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Jako, iż jest to dla mnie nowy serwer zaleca się użycie komendy `{}setup`.").format(ctx.prefix))
            return await add_react(ctx.message, False)

        elif isinstance(error, TagNotFound):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Nie znaleziono {}.").format(error.tag_name))
            return await add_react(ctx.message, False)

        elif isinstance(error, TagAlreadyExists):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Tag {} już istnieje.").format(error.tag_name))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.NSFWChannelRequired):
            await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Ten kanał nie jest nsfw."))
            return await add_react(ctx.message, False)

        elif isinstance(error, commands.CheckFailure):
            return

        else:
            traceback.print_exception(type(error), error, error.__traceback__)

            stack = 8
            traceback_text = "\n".join(traceback.format_exception(
                type(error), error, error.__traceback__, stack))
            owner = ctx.bot.get_user(ctx.bot.owner_id)

            await owner.send(
                f"Command: {ctx.command}\nGuild: {ctx.guild}\nTime: {datetime.utcnow()}```py\n{traceback_text}```")
            #return await ctx.send(_(await get_language(self.bot, ctx.guild.id), "Fatalny błąd!\n```\n{error}```").format(error=error))


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))
