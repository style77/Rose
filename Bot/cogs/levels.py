from discord.ext import commands

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def create_acc(self, user_id, guild_id):
        user = await self.bot.pg_con.fetchrow("INSERT INTO levels (user_id, guild_id) VALUES ($1, $2) RETURNING *",
                                              user_id, guild_id)
        return user

    @commands.Cog.listener()
    async def on_message(self, m):
        if not m.guild:
            return
        settings = await self.bot.pg_con.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1",
                                                  m.guild.id)
        if not settings or not settings['levels']:
            return
        if m.guild.id in [336642139381301249, 264445053596991498]:
            return
        if m.author.bot:
            return
        
        user = await self.bot.pg_con.fetchrow("SELECT * FROM levels WHERE user_id = $1 AND guild_id = $2",
                                              m.author.id, m.guild.id)

        if not user:
            user = await self.create_acc(m.author.id, m.guild.id)

        await self.bot.pg_con.execute("UPDATE levels SET messages = messages + 1 WHERE user_id = $1 AND guild_id = $2",
                                      m.author.id, m.guild.id)

        if round((user['level']*400)*2) >= user['messages']:
            await self.bot.pg_con.execute("UPDATE levels SET level = level + 1 WHERE user_id = $1 AND guild_id = $2",
                                          m.author.id, m.guild.id)
            if not settings['level_message']:
                level_msg = _(await get_language(self.bot, m.guild.id), "<@USER> awansował na <LEVEL> level.")
            else:
                level_msg = settings['level_message']
            
            level_msg = level_msg.replace("<LEVEL>", user['level']+1)
            level_msg = settings.replace_with_args(level_msg, m.author)

            return await m.channel.send(level_msg)

    @commands.command(aliases=['top', 'server_top'])
    async def servertop(self, ctx):
        levels = await self.bot.pg_con.fetch("SELECT * FROM levels WHERE guild_id = $1 ORDER BY level DESC LIMIT 10", ctx.guild.id)

        z = []
        i = 1

        for user in levels:
            member = ctx.guild.get_member(user['user_id'])
            z.append(
                f"[{i}]    {str(member):<10}  {user['level']:>6} level   {user['messages']:<4} exp\n")
            i += 1

        z.append(f"\nguild: {ctx.guild.name}")
        return await ctx.send('```' + ''.join(z) + '```')

def setup(bot):
    bot.add_cog(Levels(bot))
