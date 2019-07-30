import datetime
import typing
from io import BytesIO

import aiohttp
import discord
from discord.ext import commands

from cogs import utils


class TagNotFound(commands.CommandError):
    def __init__(self, tag):
        super().__init__(f"{tag} not found")
        self.tag_name = tag


class TagAlreadyExists(commands.CommandError):
    def __init__(self, tag):
        self.tag_name = tag['tag_name']


class Tags(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def suggest_box(self, guild_id, tag_name):
        lang = await get_language(self.bot, guild_id)
        def disambiguate(rows, query):
            if rows is None or len(rows) == 0:
                raise TagNotFound(tag_name)

            names = '\n'.join(r['tag_name'] for r in rows)
            return _(lang, "Nie znalazłem takiego tag-a. Czy chodziło Ci o\n{}").format(names)

        query = """SELECT tags.tag_name
                   FROM tags
                   WHERE guild_id=$1 AND tag_name=$2
                   ORDER BY similarity(tags.tag_name, $2) DESC
                   LIMIT 4;
                """

        return disambiguate(await self.bot.pg_con.fetch(query, str(guild_id), tag_name), tag_name)

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def tag(self, ctx, *, tag_name: str=None):
        """Pokazuje tag."""
        if not tag_name:
            raise commands.UserInputError()
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2", str(ctx.guild.id), tag_name.lower())
        if not tage:
            z = await self.suggest_box(ctx.guild.id, tag_name)
            return await ctx.send(z)
        content = tage[0]['tag_content']
        if tage[0]['img_link']:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(tage[0]['img_link']) as r:
                    file = discord.File(filename=f"{tag_name}.png", fp=BytesIO(await r.read()))
        else:
            file = None
        await ctx.send(content, file=file)
        await self.bot.pg_con.execute("UPDATE tags SET tag_uses = $1 WHERE guild_id = $2 AND tag_name = $3", tage[0]['tag_uses']+1, str(ctx.guild.id), tag_name)

    @tag.command()
    async def search(self, ctx, tag: str = None):
        """Wyszukaj tagu."""
        if tag:
            sql = """SELECT tag_name
                    FROM tags
                    WHERE guild_id=$1 AND tag_name % $2
                    ORDER BY similarity(tag_name, $2) DESC
                    LIMIT 100;
                 """
            results = await self.bot.pg_con.fetch(sql, str(ctx.guild.id), tag)

            if results:
                try:
                    p = utils.Pages(ctx, entries=tuple(r[0] for r in results), per_page=15)
                    await p.paginate(index_allowed=True)
                except Exception as e:
                    await ctx.send(e)
            else:
                await ctx.send(_(ctx.lang, "Nic nie znalazłem."))

    @tag.command(invoke_without_command=True)
    async def raw(self, ctx, *, tag: str=None):
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2", str(ctx.guild.id), tag.lower())

        clean_content = discord.utils.escape_markdown(tage[0]['tag_content'])
        clean_content.replace('<', '\\<')

        if not tage:
            z = await self.suggest_box(ctx.guild.id, tag)
            return await ctx.send(z)
        if tage[0]['img_link'] and tage[0]['tag_content']:
            await ctx.send(f"{tage[0]['img_link']}\n{clean_content}")
        elif not tage[0]['img_link'] and tage[0]['tag_content']:
            await ctx.send(f"{clean_content}")
        elif not tage[0]['tag_content'] and tage[0]['img_link']:
            await ctx.send(f"{tage[0]['img_link']}")
        await self.bot.pg_con.execute("UPDATE tags SET tag_uses = $1 WHERE guild_id = $2 AND tag_name = $3", tage[0]['tag_uses']+1, str(ctx.guild.id), tag)


    @commands.command()
    async def tags(self, ctx, member: typing.Optional[discord.Member]=None):
        """Zwraca wszystkie tagi z serwera."""
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1",str(ctx.guild.id))
        if member:
            tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_author_id = $2", str(ctx.guild.id), str(member.id))
        entries = [t['tag_name'] for t in tage]
        if len(entries) < 1:
            return await ctx.send(_(ctx.lang, "Serwer nie posiada żadnych tagów."))
        pages = utils.Pages(ctx, entries=entries)
        await pages.paginate(index_allowed=True)

    @tag.command(aliases=['add', 'make'])
    async def create(self, ctx, *, tag: str=None):
        """Stwórz tag."""
        if tag.lower() in ["search", "raw", "create", "edit", "add", "remove", "info", "claim", "top", "global"]:
            return await ctx.send(_(ctx.lang, "Nie możesz stworzyć taga o nazwie funkcyjnej."))
        z = tag.split(" - ")
        tag_name = z[0].lower()
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2", str(ctx.guild.id), tag_name.lower())
        if tage:
            raise TagAlreadyExists(tage[0])
        tag_result = "\n".join(z[1:])
        link = None
        if not tag_result:
            def check(m):
                return m.author.id == ctx.author.id and m.channel == ctx.channel

            await ctx.send(_(ctx.lang, "Wpisz teraz co ma zawierać `{}`.").format(tag_name))
            msg = await self.bot.wait_for('message', check=check)
            tag_result = msg.content
            if msg.attachments:
                link = msg.attachments[0].url

        if len(tag_result) > 2000:
            return await ctx.send(_(ctx.lang, "Tagi nie mogą posiadać więcej niż 2000 znaków."))

        if not tage:
            await self.bot.pg_con.execute("INSERT INTO tags (guild_id, tag_name, tag_content, tag_author_id, tag_created_at, tag_uses, img_link) VALUES ($1,$2,$3,$4,$5,0,$6)", str(ctx.guild.id), tag_name, str(tag_result), str(ctx.author.id), str(ctx.message.created_at),link)
            await ctx.send(_(ctx.lang, "**{}** stworzony.").format(tag_name))

    @tag.command()
    async def edit(self, ctx, *, tag_name: str=None):
        """Zedytuj tag."""
        z = tag_name.split(" - ")
        tag_name = z[0].lower()
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2", str(ctx.guild.id), tag_name)
        if not tage:
            raise TagNotFound(tag_name)
        if ctx.author.id != int(tage[0]['tag_author_id']):
            return await ctx.send(_(ctx.lang, "Ten tag nie należy do ciebie."))
        try:
            x = z[1]
            tag_result = ''.join(x)
        except IndexError:
            tag_result = None
        link = None

        def check(m):
            return m.author.id == ctx.author.id and m.channel == ctx.channel

        if not tag_result:
            await ctx.send(_(ctx.lang, "Wpisz teraz na co chcesz zeedytować {}.").format(tag_name))
            msg = await self.bot.wait_for('message', check=check)
            tag_result = msg.content
            if msg.attachments:
                link = ctx.message.attachments[0].url

        if len(tag_result) >= 2000:
            return await ctx.send(_(ctx.lang, "Tagi nie mogą posiadać więcej niż 2000 znaków."))

        await self.bot.pg_con.execute("UPDATE tags SET tag_content = $1 WHERE guild_id = $2 AND tag_name = $3", tag_result, str(ctx.guild.id), tag_name)
        if link:
            await self.bot.pg_con.execute("UPDATE tags SET tag_content = $1 AND img_link = $4 WHERE guild_id = $2 AND tag_name = $3", tag_result, str(ctx.guild.id), tag_name, link)
        await ctx.send(_(ctx.lang, "Tag zedytowany."))

    @tag.command(aliases=['delete'])
    async def remove(self, ctx, *, tag: str=None):
        """Usuń tag."""
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2",str(ctx.guild.id),tag)
        if not tage:
            raise TagNotFound(tag)
        if ctx.author.id == int(tage[0]['tag_author_id']) or ctx.author.guild_permissions.manage_guild:
            await self.bot.pg_con.execute("DELETE FROM tags WHERE guild_id = $1 AND tag_name = $2",str(ctx.guild.id),tag)
            await ctx.send(':ok_hand:')
        else:
            return await ctx.send(_(ctx.lang, "Ten tag nie należy do ciebie, ani nie masz permisji `manage_guild`, aby go usunać."))

    @tag.command(name="info")
    async def _info(self, ctx, *, tag: str=None):
        """Pokaż informacje o tagu."""
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2", str(ctx.guild.id), tag)
        if not tage:
            raise TagNotFound(tag)
        author = await self.bot.fetch_user(int(tage[0]['tag_author_id']))
        made = datetime.datetime.strptime(tage[0]['tag_created_at'],'%Y-%m-%d %H:%M:%S.%f')
        e = discord.Embed(description=_(ctx.lang, "Autor: **{}**\nUżycia: **{}**").format(author.name, tage[0]['tage_uses']), color=0xEC3B8E, timestamp=made)
        e.set_author(name=author, icon_url=author.avatar_url)
        await ctx.send(embed=e)

    @tag.command()
    async def claim(self, ctx, *, tag: str=None):
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2",str(ctx.guild.id),tag)
        if not tage:
            raise TagNotFound(tag)
        author = await self.bot.fetch_user(int(tage[0]['tag_author_id']))
        if author.id == ctx.author.id:
            return await ctx.send(_(ctx.lang, "Nie możesz zabrać swojego tag-a."))
        if author in ctx.guild.members:
            return await ctx.send(_(ctx.lang, "Właściciel tag-a ciągle jest na tym serwerze."))
        await self.bot.pg_con.execute("UPDATE tags SET tag_author_id = $1 WHERE tag_name = $2", str(ctx.author.id), str(tag))
        return await ctx.send(_(ctx.lang, "Pomyślnie zostałeś właścicielem tego taga."))

    @tag.command()
    async def top(self, ctx):
        """Top tagów pod względem użyć na serwerze."""
        top10 = await self.bot.pg_con.fetch(f'SELECT * FROM tags WHERE guild_id = $1 ORDER BY tag_uses DESC LIMIT 10', str(ctx.guild.id))
        z = ""
        inte = 0
        cor = "użyć"
        if ctx.lang == "ENG":
            cor = "uses"
        for tag in top10:
            inte += 1
            z = f"{z}#{inte}   {tag['tag_name']} - {tag['tag_uses']} {cor}\n"
        if z == "":
            return await ctx.send(_(ctx.lang, "Serwer nie posiada żadnych tagów."))
        await ctx.send(_(ctx.lang, "```{}\nRanking dla {}```").format(z, ctx.guild.id))

    @tag.group(name='global',invoke_without_command=True)
    async def global_(self, ctx, guild_id=None, *, tag: str=None):
        """Nie dodaje użyć!"""
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2",str(guild_id),tag)
        if not tage:
            z = await self.suggest_box(ctx.guild.id, tag)
            return await ctx.send(z)
        content = tage[0]['tag_content']
        if tage[0]['img_link']:
            async with aiohttp.ClientSession() as cs:
                async with cs.get(tage[0]['img_link']) as r:
                    file = discord.File(filename=f"{tag}.png", fp=BytesIO(await r.read()))
        else:
            file = None
        await ctx.send(content, file=file)

    @global_.command()
    async def info(self, ctx, guild_id=None, *, tag: str=None):
        """Informacje o globalnym tagu."""
        tage = await self.bot.pg_con.fetch("SELECT * FROM tags WHERE guild_id = $1 AND tag_name = $2",str(guild_id),tag)
        if not tage:
            raise TagNotFound(tag)
        author = await self.bot.fetch_user(int(tage[0]['tag_author_id']))
        made=datetime.datetime.strptime(tage[0]['tag_created_at'],'%Y-%m-%d %H:%M:%S.%f')
        e = discord.Embed(description=_(ctx.lang, "Autor: **{}**\nUżycia: **{}**").format(author.name, tage[0]['tag_uses']), color=0xEC3B8E, timestamp=made)
        e.set_author(name=author,icon_url=author.avatar_url)
        await ctx.send(embed=e)

def setup(bot):
    bot.add_cog(Tags(bot))
