import asyncio

from discord.ext import commands

#from cogs.utils.checks import has_todos
from cogs.utils.paginator import Pages

class Todo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def remove_todo(self, db_object):
        await self.bot.pg_con.execute("DELETE FROM todo WHERE user_id = $1 AND id = $2", db_object['user_id'], db_object['id'])

    async def create_todo(self, user_id, _id, desc):
        await self.bot.pg_con.execute("INSERT INTO todo (user_id, id, description) VALUES ($1, $2, $3)", user_id, _id, desc)

    async def clear_todo(self, todos):
        for todo in todos:
            await self.remove_todo(todo)

    async def get_todo(self, user_id, _id=None):
        if not _id:
            todo = await self.bot.pg_con.fetch("SELECT * FROM todo WHERE user_id = $1", user_id)
            if not todo:
                return None
            return todo

        todo = await self.bot.pg_con.fetch("SELECT * FROM todo WHERE user_id = $1 AND id = $2", user_id, _id)
        if not todo:
            return None
        return todo[0]

    @commands.group(invoke_without_command=True)
    async def todo(self, ctx):
        await ctx.invoke(self.bot.get_command("todo show"))

    @todo.command(aliases=['+'])
    async def add(self, ctx, *, desc=None):
        """Dodaje todo."""
        if len(desc) > 210:
            return await ctx.send(_(ctx.lang, "Opis może mieć maksymalnie 210 znaków."))

        # wszystkie id z bazy, ponizej dodaje do nich "1" i wyjdzie mi nastepne id
        _id = await self.bot.pg_con.fetch("SELECT id FROM todo WHERE user_id = $1 ORDER BY id DESC", ctx.author.id)
        if not _id:
            _id = 1
        else:
            _id = _id[0]['id']+1

        await self.create_todo(ctx.author.id, _id, desc)
        return await ctx.send(_(ctx.lang, "Dodano todo {}.").format(desc))

    @todo.command(aliases=['delete', 'r', 'del', '-', 'done'])
    async def remove(self, ctx, _id: int=None):
        """Usuwa dane todo."""

        x = await self.get_todo(ctx.author.id, _id)
        if x:
            await self.remove_todo(x)
            return await ctx.send(":ok_hand:")
        if not x:
            return await ctx.send(_(ctx.lang, "Nie masz todo, o takim id."))

    @todo.command()
    async def clear(self, ctx):
        """Czyści twoje todo."""
        x = await self.get_todo(ctx.author.id)
        if x:
            await self.clear_todo(x)
            return await ctx.send(":ok_hand:")
        if not x:
            return await ctx.send(_(ctx.lang, "Nie posiadasz żadnych todo."))

    @todo.command(aliases=['list'])
    async def show(self, ctx):
        """Pokazuje wszystkie twoje todo."""
        todos = await self.bot.pg_con.fetch("SELECT * FROM todo WHERE user_id = $1 ORDER BY id ASC", ctx.author.id)

        entries = []
        for t in todos:
            entries.append(f"#{t['id']}  {t['description']}")

        if len(entries) < 1:
            return await ctx.send(_(ctx.lang, "Nie posiadasz żadnych todo."))
        pages = Pages(ctx, entries=entries)
        await pages.paginate(index_allowed=False)
    
    @todo.command(aliases=['e'])
    async def edit(self, ctx, *, desc: str=None):
        desc = desc.split(" - ")
        id_ = int(desc[0])
        try:
            x = desc[1]
            content = ''.join(x)
        except IndexError:
            content = None
        todo = await self.bot.pg_con.fetch("SELECT * FROM todo WHERE user_id = $1 AND id = $2", ctx.author.id, id_)
        if not todo:
            return await ctx.send(_(ctx.lang, "Nie masz todo, o takim id."))
        if not content:
            def check(m):
                return m.author.id == ctx.author.id and m.channel == ctx.channel

            await ctx.send(_(ctx.lang, "Wpisz teraz na co chcesz zeedytować {}.").format(todo[0]['description']))
            try:
                msg = await self.bot.wait_for('message', check=check, timeout=225)
            except asyncio.TimeoutError:
                return await ctx.send(_(ctx.lang, "Czas na odpowiedź minął."))
            content = msg.content

        await self.bot.pg_con.execute("UPDATE todo SET description = $1 WHERE user_id = $2 AND id = $3", content, ctx.author.id, id_)
        await ctx.send(":ok_hand:")

def setup(bot): 
    bot.add_cog(Todo(bot))
