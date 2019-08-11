from discord.ext import commands

class NoTodos(commands.CheckFailure):
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
