from cogs.classes.converters import EasyTime, PrettyTime, FutureTime, EasyOneDayTime, UserFriendlyTime, human_timedelta
from discord.ext import commands, tasks

import discord
import asyncio
import asyncpg

from datetime import datetime, timedelta

class Reminder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = self.dispatch_timers.start()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)

    def cog_unload(self):
        self._task.cancel()

    async def get_active_timers(self):
        t = await self.bot.pg_con.fetch("SELECT * FROM timers")
        return t

    async def get_user_timers(self, user_id):
        user_timers = await self.bot.pg_con.fetch("SELECT * FROM timers WHERE user_id = $1", user_id)
        return user_timers

    async def remove_reminder(self, db):
        await self.bot.pg_con.execute("DELETE FROM timers WHERE user_id = $1 AND reminder = $2", db['user_id'], db['reminder'])

    @tasks.loop(seconds=1)
    async def dispatch_timers(self):
        try:
            for timer in await self.get_active_timers():
                if timer['date'] <= datetime.now():
                    self.bot.dispatch("reminder_timer_complete", timer)

        except asyncio.CancelledError:
            pass
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.dispatch_timers.start()
        except Exception as e:
            print(e)

    @dispatch_timers.before_loop
    async def dispatch_timers_b4(self):
        await self.bot.wait_until_ready()

    async def create_reminder(self, user_id, channel_id, date, description, message_id, now):
        await self.bot.pg_con.execute("INSERT INTO timers (user_id, channel, date, reminder, message_id, now) VALUES ($1, $2, $3, $4, $5, $6)", user_id, channel_id, date, description, message_id, now)

    @commands.group(aliases=['reminder'], invoke_without_command=True)
    async def remind(self, ctx, *, date: UserFriendlyTime(commands.clean_content, default='\u2026')):
        lang = ctx.lang
        #if date.dt is False and reminder is not None:
            #return await ctx.send(_(lang, "Ten czas jest błędny. Porady dotyczące czasu są w dokumentacji `{}docs`.").format(ctx.prefix))
        if not date:
            raise commands.UserInputError()
        #if not date:
            #return await ctx.send(_(lang, "Ten czas jest błędny. Porady dotyczące czasu są w dokumentacji `{}docs`.").format(ctx.prefix))
        now = ctx.message.created_at + timedelta(hours=2) if ctx.lang == "PL" else ctx.message.created_at
        print(now)
        await self.create_reminder(ctx.author.id, ctx.channel.id, date.dt, date.arg, ctx.message.id, now)
        delta = human_timedelta(date.dt, source=now)
        return await ctx.send(_(lang, "Dodano przypomnienie za {}.").format(date.dt))

    @remind.command(name='list')
    async def list_(self, ctx):
        lang = ctx.lang
        timers = await self.get_user_timers(ctx.author.id)
        if not timers:
            return await ctx.send(_(lang, "Nie masz żadnych oczekujących przypomnień."))
        p = []
        for t in timers:
            p.append(f"{t['reminder']} za {PrettyTime(lang).convert(t['date'], reverse=True)}")
        p = '\n'.join(p)
        return await ctx.send(f"```\n{p}\n```")

    @remind.command()
    async def remove(self, ctx, *, reminder=None):
        timer = await self.bot.pg_con.fetch("SELECT * FROM timers WHERE user_id = $1 AND reminder = $2", ctx.author.id, reminder)
        if not timer:
            return await ctx.send(_(ctx.lang, "Nie masz takiego przypomnienia."))
        await self.remove_reminder(timer[0])
        return await ctx.send(_(ctx.lang, "Usunięto przypomnienie."))

    @remind.command()
    async def edit(self, ctx, *, reminder=None):
        timer = await self.bot.pg_con.fetch("SELECT * FROM timers WHERE user_id = $1 AND reminder = $2", ctx.author.id, reminder)
        if not timer:
            return await ctx.send(_(ctx.lang, "Nie masz takiego przypomnienia."))

        old_rem = timer[0]['reminder']

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        await ctx.send(_(ctx.lang, "Wpisz teraz na co chcesz zmienić {}.").format(reminder))
        msg = await self.bot.wait_for('message', check=check, timeout=120)
        if msg.content.lower() == timer[0]['reminder'].lower():
            return await ctx.send(_(ctx.lang, "Treść nowego przypomnienia nie może być taka sama jak starego."))
        await self.bot.pg_con.execute("UPDATE timers SET reminder = $1 WHERE user_id = $2 AND reminder = $3", msg.content, ctx.author.id, old_rem)
        return await ctx.send(_(ctx.lang, "Zedytowano przypomnienie."))

    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer):
        #r = PrettyTime(lang).convert(timer['now'])
        r = timer['now']
        #if r != "właśnie teraz":
            #r = r + " temu"
            #if lang == "ENG":
                #r = r + " ago"

        channel = self.bot.get_channel(timer['channel'])
        if channel is None:
            author = self.bot.get_user(timer['user_id'])
            try:
                channel = await author.create_dm()
            except discord.HTTPException:
                return
        

        now = timer['now']
        r = human_timedelta(now, source=timer['date'])

        guild_id = channel.guild.id if isinstance(
            channel, discord.TextChannel) else '@me'
        msg = f"<@{timer['user_id']}>, {r}: {timer['reminder']}"

        try:
            z = await channel.fetch_message(timer['message_id'])
            # msg = f'{msg}\n<https://discordapp.com/channels/{guild_id}/{channel.id}/{message_id}>'
            msg = f"{msg}\n\n{z.jump_url}"
        except:
            msg = msg

        await channel.send(msg)
        await self.remove_reminder(timer)

def setup(bot):
    bot.add_cog(Reminder(bot))
