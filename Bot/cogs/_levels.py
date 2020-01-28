import asyncio
import math
import random
from collections import defaultdict, Counter

from discord.ext import commands, tasks

from .classes.other import Plugin

LEVEL_ALG_MAP = {
    1: 350,
    2: 700,
    3: 1450
}

EXP_MAP = {
    1: (4, 10),
    2: (2, 8),
    3: (1, 6)
}

# COOLDOWN_MAP = {
#     0: ,
#     1: ,
#     2:
# }


class Levels(Plugin):
    def __init__(self, bot):
        super().__init__(bot)

        self._bulk_data = defaultdict()
        self._batch_lock = asyncio.Lock(loop=bot.loop)

        bulk_insert_ = self.bulk_insert.start()
        bulk_insert_.add_done_callback(self.exception_catching_callback)

        self._cd = commands.CooldownMapping.from_cooldown(1.0, 4.5, commands.BucketType.user)

    def cog_unload(self):
        self.bulk_insert.stop()

    def exception_catching_callback(self, task):
        if task.exception():
            task.print_stack()

    @tasks.loop(seconds=5.0)
    async def bulk_insert(self):
        await self.bot.wait_until_ready()

        async with self._batch_lock:
            async with self.bot.db.acquire():
                for user_id in self._bulk_data:
                    user = await self.get_guild_profile(user_id, self._bulk_data[user_id]['guild_id'])

                    query = "UPDATE levels SET level = $1, exp = $2 WHERE user_id = $3 AND guild_id = $4;"
                    await self.bot.db.execute(query, self._bulk_data[user_id]['new_level'],
                                              user['exp'] + self._bulk_data[user_id]['new_exp'], user_id,
                                              self._bulk_data[user_id]['guild_id'])

            self._bulk_data.clear()

    async def level_up(self, exp, guild):
        m = LEVEL_ALG_MAP[guild.leveling_type]

        if exp >= (m * self._level_from_exp(exp, guild.leveling_type)):
            return True
        else:
            return False

    def _level_from_exp(self, exp, leveling_type):
        m = LEVEL_ALG_MAP[leveling_type]
        return math.ceil(abs(exp / m))

    async def get_guild_profile(self, author_id, guild_id):
        user = await self.bot.db.fetchrow("SELECT * FROM levels WHERE user_id = $1 AND guild_id = $2;", author_id,
                                          guild_id)
        if not user:
            user = await self.bot.db.fetchrow("INSERT INTO levels (user_id, guild_id) VALUES ($1, $2) RETURNING *;",
                                              author_id, guild_id)
        return user

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if not message.guild:
            return

        bucket = self._cd.get_bucket(message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            return
        else:
            user = await self.get_guild_profile(message.author.id, message.guild.id)
            guild = await self.bot.get_guild_settings(message.guild.id)

            if not guild.levels:
                return

            if message.author.id in self._bulk_data:
                exp = new_exp = self._bulk_data[message.author.id]['new_exp'] + random.choice(EXP_MAP[guild.leveling_type])
            else:
                exp = new_exp = random.choice(EXP_MAP[guild.leveling_type])

            if await self.level_up(exp, guild):
                new_level = user['level'] + 1

                lang = self.bot.get_language_object(guild.lang)

                await message.channel.send(lang['user_level_up'].format(message.author.mention, new_level, exp))
            else:
                new_level = user['level']

            self._bulk_data[message.author.id] = {'new_level': new_level, 'new_exp': new_exp, 'guild_id': message.guild.id}

    @commands.command()
    async def servertop(self, ctx):
        top = await self.bot.db.fetch("SELECT * FROM levels WHERE guild_id = $1 ORDER BY exp DESC;",
                                      ctx.guild.id)

        z = []

        # for i, user in enumerate(top):
        #     member = ctx.guild.get_member(user['user_id'])
        #     z.append(
        #         f"[{i+1}]    {str(member)}{abs(len(str(member))-19) * ' '}{user['level']} level{abs(len(str(user['level']))-) * ' '}{user['exp']} exp\n")
        #
        # z.append(f"\nguild: {ctx.guild.name}")
        # await ctx.send('```' + ''.join(z) + '```')

        for i, user in enumerate(top):
            member = ctx.guild.get_member(user['user_id'])
            z.append(f"**#{i+1}** {str(member)}  level: **{user['level']}** | exp: **{user['exp']}**")

        await ctx.paginate(title="Server Top", author=ctx.guild, entries=z, footer=f"Guild: {ctx.guild.name}")

def setup(bot):
    bot.add_cog(Levels(bot))
