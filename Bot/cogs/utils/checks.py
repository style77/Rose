from discord.ext import commands


def is_guild_owner():
    async def predicate(ctx):
        return ctx.guild and ctx.guild.owner == ctx.author
    return commands.check(predicate)


def is_staff():
    async def predicate(ctx):
        return ctx.author.id in [185712375628824577, 403600724342079490]
    return commands.check(predicate)


def has_premium():
    async def predicate(ctx):
        t = ctx.bot.db.fetchrow("SELECT * FROM members WHERE id = $1", ctx.author.id)
        if t:
            return True
        raise commands.CheckFailure(ctx.lang['no_premium'].format(ctx.bot.application_info.owner))
    return commands.check(predicate)
