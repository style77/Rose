import asyncio

import discord
from dataclasses import dataclass
from discord.ext import commands
from discord.utils import escape_mentions

# from Bot.cogs.utils import Pages  todo wait for 1.3 and create your own

from .classes.other import Plugin
from .utils.misc import clean_text


class TodoFinder(commands.Converter):
    async def convert(self, ctx, argument):

        query = "SELECT * FROM todo WHERE user_id = {} AND {} = {}"

        if argument.isdigit():  # because in discord everything is string
            q = query.format(ctx.author.id, 'id', argument)
            first = await ctx.bot.db.fetchrow(q)
            if not first:
                return None
            return first
        elif isinstance(argument, str):
            q = query.format(ctx.author.id, 'description', f"'{argument}'")
            second = await ctx.bot.db.fetchrow(q)
            if not second:
                return None
            return second
        else:
            return None


@dataclass
class TodoObject:
    req: dict

    user_id: int
    id: int
    description: str

    def __init__(self, req):
        self.req = req
        self.user_id = req['user_id']
        self.id = req['id']
        self.description = req['description']

    def to_dict(self):
        return dict(self.req)


class Todo(Plugin):
    def __init__(self, bot):
        super().__init__(bot, command_attrs={'not_turnable': True})
        self.bot = bot

    async def add_todo(self, data: TodoObject):
        data = data.to_dict()

        await self.bot.db.execute(f"INSERT INTO todo (id, description, user_id) VALUES ($1, $2, $3)", data['id'], data['description'], data['user_id'])

    async def get_todo(self, user_id, *, id_=None, order="ASC"):

        if order not in ['ASC', 'DESC']:
            raise ValueError("Wrong order given.")

        if id_:
            todo = await self.bot.db.fetch("SELECT * FROM todo WHERE user_id = $1 AND id = $2", user_id, id_)

        else:
            todo = await self.bot.db.fetch(f"SELECT * FROM todo WHERE user_id = $1 ORDER BY id {order}", user_id)

        if not todo:
            return None
        return todo

    @commands.group(invoke_without_command=True)
    async def todo(self, ctx):
        todos = await self.get_todo(ctx.author.id)

        entries = []

        if not todos:
            return await ctx.send(ctx.lang['no_todos'])

        for t in todos:
            entries.append(f"#{t['id']}  {t['description']}")

        await ctx.paginate(entries=entries, colour=3553598, author=ctx.author)

    @todo.command(aliases=['all'])
    async def list(self, ctx):
        await ctx.invoke(self.todo)

    @todo.command(aliases=['+'])
    async def add(self, ctx, *, desc: commands.clean_content):
        if len(desc) > 210:
            return await ctx.send(ctx.lang['todo_max_lenght'])

        # wszystkie id z bazy, ponizej dodaje do nich "1" i wyjdzie mi nastepne id
        _id = await self.get_todo(ctx.author.id, order="DESC")
        if not _id:
            _id = 1
        else:
            _id = _id[0]['id'] + 1

        todo = TodoObject({'id': _id, 'user_id': ctx.author.id, 'description': desc})

        await self.add_todo(todo)
        await ctx.send(f"{ctx.lang['added_todo']} {escape_mentions(desc)}.")

    @todo.command(aliases=['e'])
    async def edit(self, ctx, *, desc: str):
        desc = desc.split(" - ")
        id_ = int(desc[0])

        try:
            x = desc[1]
            content = ''.join(x)
        except IndexError:
            content = None

        todo = await self.get_todo(ctx.author.id, id_=id_)
        if not todo:
            return await ctx.send(ctx.lang['no_todo_with_id'])

        if not content:
            def check(m):
                return m.author.id == ctx.author.id and m.channel == ctx.channel

            await ctx.send(f"{ctx.lang['tell_todo_edit']} {todo[0]['description']}.")
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=225)
            except asyncio.TimeoutError:
                return await ctx.send(ctx.lang['TimeoutError'])
            content = msg.content

        await self.bot.pg_con.execute("UPDATE todo SET description = $1 WHERE user_id = $2 AND id = $3", content,
                                      ctx.author.id, id_)
        await ctx.send(":ok_hand:")

    @todo.command()
    async def show(self, ctx, *, catch: TodoFinder):
        if not catch:
            return await ctx.send(ctx.lang['todo_not_found'])

        todo = await self.get_todo(ctx.author.id, id_=catch['id'])

        e = discord.Embed(color=0x36393E)

        keys = ['description', 'id']
        for key in keys:
            value = todo[0][key]
            e.add_field(name=key, value=value, inline=False)

        await ctx.send(embed=e)

    @todo.command(aliases=['-'])
    async def remove(self, ctx, *, catch: TodoFinder):
        todos = await self.get_todo(ctx.author.id)
        if not todos:
            return await ctx.send(ctx.lang['no_todos'])

        if not catch:
            return await ctx.send(ctx.lang['todo_not_found'])

        confirmation = await ctx.confirm(ctx.lang['confirm_deleting_todo'], ctx.author)
        if confirmation is False:
            return await ctx.send(ctx.lang['abort'])
        else:
            query_1 = "DELETE FROM todo WHERE user_id = $1 AND id = $2"
            query_2 = "UPDATE todo SET id = id - 1 WHERE user_id = $1 AND id > $2"

            await self.bot.db.execute(query_1, ctx.author.id, catch['id'])
            await self.bot.db.execute(query_2, ctx.author.id, catch['id'])

            await ctx.send(ctx.lang['removed_todo'])

    @todo.command(name="clear", aliases=['c'])
    async def clear_(self, ctx):
        todos = await self.get_todo(ctx.author.id)
        if not todos:
            return await ctx.send(ctx.lang['no_todos'])

        confirmation = await ctx.confirm(ctx.lang['confirm_clearing_todo'], ctx.author)

        if confirmation is False:
            return await ctx.send(ctx.lang['abort'])
        else:
            query = "DELETE FROM todo WHERE user_id = $1"

            await self.bot.db.execute(query, ctx.author.id)

            await ctx.send(ctx.lang['cleared_todo'])


def setup(bot):
    bot.add_cog(Todo(bot))
