from discord.ext import commands


class NoTodos(commands.CommandError):
    pass


class NoPremium(commands.CommandError):
    pass


def is_guild_owner():
    async def predicate(ctx):
        return ctx.guild and ctx.guild.owner == ctx.author
    return commands.check(predicate)


def has_todos():
    async def predicate(ctx):
        t = ctx.bot.pg_con("SELECT * FROM todo WHERE user_id = $1", ctx.author.id)
        if t:
            return True
        raise NoTodos()
    return commands.check(predicate)


def has_premium():
    async def predicate(ctx):
        t = ctx.bot.pg_con.fetchrow("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if t:
            return True
        raise NoPremium()
    return commands.check(predicate)


def is_staff():
    async def predicate(ctx):
        return ctx.author.id in [185712375628824577, 403600724342079490]
    return commands.check(predicate)
