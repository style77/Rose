import asyncio
import io
import json
from collections import defaultdict, Counter
from datetime import datetime

import asyncpg
import discord
from discord.ext import commands, tasks

from .classes.other import Plugin
from .moderator import EMOJI_REGEX

# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/emoji.py sorry but i just love that idea and
# i dont have time to write this on my own
from .utils import get_language


def partial_emoji(argument, *, regex=EMOJI_REGEX):
    if argument.isdigit():
        # assume it's an emoji ID
        return int(argument)

    m = regex.match(argument)
    if m is None:
        raise commands.BadArgument("That's not a custom emoji...")
    return int(m.group(1))


class Emoji(Plugin):
    def __init__(self, bot):
        super().__init__(bot)

        self._batch_of_data = defaultdict(Counter)
        self._batch_lock = asyncio.Lock(loop=bot.loop)

        bulk_insert_ = self.bulk_insert.start()
        bulk_insert_.add_done_callback(self.exception_catching_callback)

    def cog_unload(self):
        self.bulk_insert.stop()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

        if message.author.bot:
            return  # no bots.

        matches = EMOJI_REGEX.findall(message.content)
        if not matches:
            return

        async with self._batch_lock:
            self._batch_of_data[message.guild.id].update(map(int, matches))

    def exception_catching_callback(self, task):
        if task.exception():
            task.print_stack()

    @tasks.loop(seconds=30.0)
    async def bulk_insert(self):
        await self.bot.wait_until_ready()

        async with self._batch_lock:
            transformed = [
                {'guild': guild_id, 'emoji': emoji_id, 'added': count}
                for guild_id, data in self._batch_of_data.items()
                for emoji_id, count in data.items()
            ]

            async with self.bot.db.acquire():
                # async with self.bot.db.transaction():
                for guild in transformed:
                    query = f"""INSERT INTO emoji_stats (guild_id, emoji_id, total) VALUES ($1, $2, $3)
                                ON CONFLICT (guild_id, emoji_id) DO UPDATE
                                SET total = emoji_stats.total + excluded.total;
                             """
                    await self.bot.db.execute(query, guild['guild'], guild['emoji'], guild['added'])

            self._batch_of_data.clear()

    def emoji_fmt(self, emoji_id, count, total, lang):
        emoji = self.bot.get_emoji(emoji_id)
        if emoji is None:
            name = f'[\N{WHITE QUESTION MARK ORNAMENT}](https://cdn.discordapp.com/emojis/{emoji_id}.png)'
            emoji = discord.Object(id=emoji_id)
        else:
            name = str(emoji)

        per_day = self.usage_per_day(emoji.created_at, count)
        p = count / total

        return lang['w_name_emoji_uses'].format(name, count, f"{p:.1%}", f"{per_day:.1f}")

    async def get_guild_stats(self, ctx):
        e = discord.Embed(color=self.bot.color)

        query = """SELECT
                   COALESCE(SUM(total), 0) AS "Count",
                   COUNT(*) AS "Emoji"
                   FROM emoji_stats
                   WHERE guild_id=$1
                   GROUP BY guild_id;
                """
        record = await self.bot.db.fetchrow(query, ctx.guild.id)
        if record is None:
            return await ctx.send(ctx.lang['no_custom_emoji_guild'])

        total = record['Count']
        emoji_used = record['Emoji']
        per_day = self.usage_per_day(ctx.me.joined_at, total)
        e.set_footer(text=ctx.lang['emoji_uses'].format(total, emoji_used, f"{per_day:.2f}"))

        query = """SELECT emoji_id, total
                   FROM emoji_stats
                   WHERE guild_id=$1
                   ORDER BY total DESC
                   LIMIT 10;
                """

        top = await self.bot.db.fetch(query, ctx.guild.id)

        e.description = '\n'.join(f'{i}. {self.emoji_fmt(emoji, count, total, ctx.lang)}' for i, (emoji, count) in enumerate(top, 1))
        await ctx.send(embed=e)

    async def get_emoji_stats(self, ctx, emoji_id):
        e = discord.Embed(color=self.bot.color)
        cdn = f'https://cdn.discordapp.com/emojis/{emoji_id}.png'

        async with self.bot.session.get(cdn) as resp:
            if resp.status == 404:
                e.description = "This isn't a valid emoji."
                e.set_thumbnail(url='https://this.is-serious.business/09e106.jpg')
                return await ctx.send(embed=e)

        e.set_thumbnail(url=cdn)

        # valid emoji ID so let's use it
        query = """SELECT guild_id, SUM(total) AS "Count"
                   FROM emoji_stats
                   WHERE emoji_id=$1
                   GROUP BY guild_id;
                """

        records = await self.bot.db.fetch(query, emoji_id)
        transformed = {k: v for k, v in records}
        total = sum(transformed.values())

        dt = discord.utils.snowflake_time(emoji_id)

        try:
            count = transformed[ctx.guild.id]
            per_day = self.usage_per_day(dt, count)
            value = ctx.lang['s_emoji_uses'].format(count, f"{count / total:.2%}", f"{per_day:.2f}")
        except KeyError:
            value = 'error'

        e.add_field(name='Guild Stats', value=value, inline=False)

        # global stats
        per_day = self.usage_per_day(dt, total)
        value = ctx.lang['s_emoji_uses_2'].format(total, f"{per_day:.2f}")
        e.add_field(name=ctx.lang['global_stats'], value=value, inline=False)
        await ctx.send(embed=e)

    @commands.group(invoke_without_command=True, aliases=['emoji_stats'])
    @commands.guild_only()
    async def emojistats(self, ctx, *, emoji: partial_emoji = None):
        """Shows you statistics about the emoji usage in this server.
        If no emoji is given, then it gives you the top 10 emoji used.
        """

        if emoji is None:
            await self.get_guild_stats(ctx)
        else:
            await self.get_emoji_stats(ctx, emoji)

    def usage_per_day(self, dt, usages):
        tracking_started = datetime(2019, 12, 26)
        now = datetime.utcnow()
        if dt < tracking_started:
            base = tracking_started
        else:
            base = dt

        days = (now - base).total_seconds() / 86400  # 86400 seconds in a day
        if int(days) == 0:
            return usages
        return usages / days

    @emojistats.command(name='server', aliases=['guild'])
    @commands.guild_only()
    async def emojistats_guild(self, ctx):
        """Shows you statistics about the local server emojis in this server."""
        emoji_ids = [e.id for e in ctx.guild.emojis]

        if not emoji_ids:
            await ctx.send(ctx.lang['no_custom_emoji_guild'])

        query = """SELECT emoji_id, total
                   FROM emoji_stats
                   WHERE guild_id=$1 AND emoji_id = ANY($2::bigint[])
                   ORDER BY total DESC
                """

        e = discord.Embed(colour=self.bot.color)  # Emoji Leaderboard
        records = await self.bot.db.fetch(query, ctx.guild.id, emoji_ids)

        total = sum(a for _, a in records)
        emoji_used = len(records)
        per_day = self.usage_per_day(ctx.me.joined_at, total)
        e.set_footer(text=ctx.lang['emoji_uses'].format(total, emoji_used, f"{per_day:.2f}"))
        top = records[:10]
        value = '\n'.join(self.emoji_fmt(emoji, count, total, ctx.lang) for (emoji, count) in top)
        e.add_field(name=f'Top {len(top)}', value=value or f"{ctx.lang['nothing']}...")

        record_count = len(records)
        if record_count > 10:
            bottom = records[-10:] if record_count >= 20 else records[-record_count + 10:]
            value = '\n'.join(self.emoji_fmt(emoji, count, total, ctx.lang) for (emoji, count) in bottom)
            e.add_field(name=f'Bottom {len(bottom)}', value=value)

        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(Emoji(bot))
