import discord
from dataclasses import dataclass

from datetime import datetime

from discord.ext import commands

from .classes.other import Plugin
from .utils import clean_text, escape_mentions, get_language


# class TagObject(dataclass):
#     name: str
#     guild_id: int
#     owner_id: int
#     content: str
#     uses: int
#     created_at: datetime
#
#
# class TagAliasObject(dataclass):
#     alias: str
#     orginal: str
#     guild_id: int
#     owner_id: int
#     uses: int
#     created_at: datetime

class TagObject:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, item):
        return self.data.get(item, None)


class Tags(Plugin):
    def __init__(self, bot):
        super().__init__(bot)

        self._reserved_tags = dict()

    async def cog_check(self, ctx):
        return ctx.guild is not None

    def is_tag_being_made(self, name, guild_id):
        try:
            tags = self._reserved_tags[guild_id]
        except KeyError:
            return False

        tag = tags.get(name, None)
        return tag is not None

    async def get_tag_suggest_box(self, guild_id, name):

        lang = self.bot.get_language_object(await get_language(self.bot, guild_id))

        def disambiguate(rows, query):
            if rows is None or len(rows) == 0:
                raise commands.BadArgument(lang['tag_doesnt_exist'].format(clean_text(name)))

            names = '\n'.join(f"`{clean_text(r['name'])}`" for r in rows)
            raise commands.BadArgument(lang['tag_doesnt_exist_did_you_mean'].format(clean_text(name), names))

        con = self.bot.db

        query = """SELECT tags.name, tags.content
                   FROM tags_lookup 
                   INNER JOIN tags ON tags.name = tags.name
                   WHERE tags.guild_id = $1 AND LOWER(tags.name) = $2"""

        row = await con.fetchrow(query, guild_id, name)
        if row is None:
            query = """SELECT     tags.name
                       FROM       tags
                       WHERE      tags.guild_id=$1 AND tags.name % $2
                       ORDER BY   similarity(tags.name, $2) DESC
                       LIMIT 3;
                    """

            return disambiguate(await con.fetch(query, guild_id, name), name)
        else:
            return row

    @commands.group(invoke_without_command=True)
    async def tag(self, ctx, *, name):
        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await self.get_tag_suggest_box(ctx.guild.id, name)
            else:
                alias_name = tag.alias
                tag = await self.get_tag(ctx.guild.id, tag.orginal)

        await ctx.send(tag.content)

        if not alias:
            query = "UPDATE tags SET uses = uses + 1 WHERE name = $1 AND guild_id = $2"
            await self.bot.db.execute(query, tag.name, ctx.guild.id)
        else:
            query = "UPDATE tags_lookup SET uses = uses + 1 WHERE alias = $1 AND guild_id = $2"
            await self.bot.db.execute(query, alias_name, ctx.guild.id)

    @tag.group(invoke_without_command=True)
    async def raw(self, ctx, *, name):
        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await self.get_tag_suggest_box(ctx.guild.id, name)
            else:
                alias_name = tag.alias
                tag = await self.get_tag(ctx.guild.id, tag.orginal)

        first_step = discord.utils.escape_markdown(tag.content)
        await ctx.send(first_step.replace('<', '\\<'))

        if not alias:
            query = "UPDATE tags SET uses = uses + 1 WHERE name = $1 AND guild_id = $2"
            await self.bot.db.execute(query, tag.name, ctx.guild.id)
        else:
            query = "UPDATE tags_lookup SET uses = uses + 1 WHERE alias = $1 AND guild_id = $2"
            await self.bot.db.execute(query, alias_name, ctx.guild.id)

    @commands.command()
    async def tags(self, ctx, *, member: discord.Member = None):
        await ctx.invoke(self._list, member=member)

    @tag.command(name='list')
    async def _list(self, ctx, *, member: discord.Member = None):
        member = member or ctx.author

        query = """SELECT name
                   FROM tags
                   WHERE guild_id=$1 AND owner_id=$2
                   ORDER BY name
                """

        rows = await self.bot.db.fetch(query, ctx.guild.id, member.id)

        if rows:
            try:
                await ctx.paginate(author=member, entries=tuple(r[0] for r in rows))
            except Exception as e:
                await ctx.send(e)
        else:
            await ctx.send(ctx.lang['member_has_no_tags'].format(member))

    @tag.command(name='all')
    async def _all(self, ctx):
        query = """SELECT name
                   FROM tags
                   WHERE guild_id=$1
                """

        rows = await self.bot.db.fetch(query, ctx.guild.id)

        if rows:
            entries = sorted(tuple(r[0] for r in rows))
            try:
                await ctx.paginate(entries=entries, per_page=20)
            except Exception as e:
                await ctx.send(e)
        else:
            await ctx.send(ctx.lang['nothing_found'])

    async def run_interactive_creation(self, ctx, name=None):
        c = await ctx.confirm(ctx.lang['tag_creation_info_0'], ctx.author, type_='message',
                              prompt=['yes', 'tak', '1', 'true'])
        if c:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            if not name:
                await ctx.send(ctx.lang['tag_creation_info_1'])
                m = await self.bot.wait_for('message', check=check)
                if m:
                    name = m.content
                    if ctx.guild.id not in self._reserved_tags:
                        self._reserved_tags[ctx.guild.id] = list()
                    self._reserved_tags[ctx.guild.id].append(name)
                else:
                    return None, None

            await ctx.send(ctx.lang['tag_creation_info_2'].format(clean_text(name)))
            m = await self.bot.wait_for('message', check=check)
            if m:
                content = m.content
            else:
                return None, None

            self._reserved_tags[ctx.guild.id].remove(name)
            return name, content

        else:
            return None, None

    async def get_tag(self, guild_id, name, *, alias=False):
        if not alias:
            query = "SELECT * FROM tags WHERE guild_id = $1 AND lower(name) = $2"
        else:
            query = "SELECT * FROM tags_lookup WHERE guild_id = $1 AND lower(alias) = $2"

        t = await self.bot.db.fetchrow(query, guild_id, name.lower())
        if not t:
            return None
        return TagObject(t)

    async def tag_exist(self, name, guild_id, *, alias=False):
        tag = await self.get_tag(guild_id, name, alias=alias)
        if tag:
            return True
        else:
            return False

    @tag.command(alias=['make'])
    async def create(self, ctx, *, content=None):
        try:
            name, content = content.rsplit(' - ')
        except ValueError:
            name, content = await self.run_interactive_creation(ctx)

        if (name and content) is None:
            return await ctx.send(ctx.lang['abort'])

        root = self.bot.get_command('tag')
        if name in root.all_commands:
            raise commands.BadArgument('This tag name starts with a reserved word.')  # todo translate

        if await self.tag_exist(name, ctx.guild.id):
            raise commands.BadArgument(ctx.lang['tag_already_exist'].format(clean_text(name)))

        if self.is_tag_being_made(name, ctx.guild.id):
            raise commands.BadArgument(ctx.lang['tag_being_made'])

        query = "INSERT INTO tags (name, content, guild_id, owner_id, created_at) VALUES ($1, $2, $3, $4, $5)"
        await self.bot.db.execute(query, name, escape_mentions(content), ctx.guild.id, ctx.author.id, ctx.message.created_at)
        await ctx.send(ctx.lang['created_tag'].format(clean_text(name)))

    @tag.command()
    async def alias(self, ctx, alias, orginal):
        if await self.tag_exist(alias, ctx.guild.id, alias=True):
            raise commands.BadArgument(ctx.lang['alias_already_exist'].format(clean_text(alias)))

        if not await self.tag_exist(orginal, ctx.guild.id):
            raise commands.BadArgument(ctx.lang['tag_doesnt_exist'].format(clean_text(orginal)))

        root = self.bot.get_command('tag')
        if alias in root.all_commands:
            raise commands.BadArgument('This tag name starts with a reserved word.')  # todo translate

        query = "INSERT INTO tags_lookup (alias, orginal, guild_id, owner_id, created_at) VALUES ($1, $2, $3, $4, $5)"
        await self.bot.db.execute(query, alias, orginal, ctx.guild.id, ctx.author.id, ctx.message.created_at)
        await ctx.send(ctx.lang['created_alias'].format(clean_text(alias), clean_text(orginal)))

    async def _send_info(self, ctx, record, *, alias=False):
        e = discord.Embed(color=self.bot.color)

        if alias:
            e.title = record['alias']
            e.timestamp = record['created_at']
            e.set_footer(text='Alias created at')  # todo not important translation

            user = self.bot.get_user(record['owner_id']) or (await self.bot.fetch_user(record['owner_id']))
            e.set_author(name=str(user), icon_url=user.avatar_url)

            e.add_field(name='Owner', value=f"<@{record['owner_id']}>")
            e.add_field(name='Original', value=record['orginal'])
            e.add_field(name='Uses', value=record['uses'])
        else:
            e.title = record['name']
            e.timestamp = record['created_at']
            e.set_footer(text='Tag created at')  # todo not important translation

            user = self.bot.get_user(record['owner_id']) or (await self.bot.fetch_user(record['owner_id']))
            e.set_author(name=str(user), icon_url=user.avatar_url)

            e.add_field(name='Owner', value=f"<@{record['owner_id']}>")

            query = """SELECT (
                           SELECT COUNT(*)
                           FROM tags second
                           WHERE (second.uses, second.name) >= (first.uses, first.name)
                             AND second.guild_id = first.guild_id
                       ) AS rank
                       FROM tags first
                       WHERE first.name=$1
                    """

            rank = await self.bot.db.fetchrow(query, record['name'])

            if rank is not None:
                e.add_field(name='Rank', value=rank['rank'])

            aliases = await self.bot.db.fetch("SELECT * FROM tags_lookup WHERE lower(orginal) = $1 AND guild_id = $2",
                                              record['name'].lower(), ctx.guild.id)

            if aliases:
                z = ', '.join(f"`{alias['alias']}`" for alias in aliases)
                e.add_field(name='Aliases', value=z)
            e.add_field(name='Uses', value=record['uses'])
        await ctx.send(embed=e)

    @tag.command()
    async def info(self, ctx, *, name):
        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await self.get_tag_suggest_box(ctx.guild.id, name)

        await self._send_info(ctx, tag.data, alias=alias)

    @tag.command()
    async def claim(self, ctx, *, name):
        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await self.get_tag_suggest_box(ctx.guild.id, name)

        try:
            member = ctx.guild.get_member(tag.owner_id) or await ctx.guild.fetch_member(tag.owner_id)
        except discord.NotFound:
            member = None

        if member is not None:
            return await ctx.send(ctx.lang['tag_owner_still_in_server'].format(clean_text(name)))

        if alias:
            query = "UPDATE tags_lookup SET owner_id = $1 WHERE alias = $2 AND guild_id = $3"
            msg = ctx.lang['transfered_alias']
        else:
            query = "UPDATE tags SET owner_id = $1 WHERE name = $2 AND guild_id = $3"
            msg = ctx.lang['transfered_tag']

        await self.bot.db.execute(query, name, ctx.guild.id)
        await ctx.send(msg)

    @tag.command()
    async def transfer(self, ctx, member: discord.Member, *, name):
        if member.bot:
            raise commands.BadArgument(ctx.lang['cant_transfer_tag_to_bot'])

        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await ctx.send(ctx.lang['tag_doesnt_exist'].format(clean_text(name)))

        async with self.bot.db.acquire():
            #async with self.bot.db.transaction():
            if alias:
                query = "UPDATE tags_lookup SET owner_id = $1 WHERE alias = $2 AND guild_id = $3"
                name = tag.alias
            else:
                query = "UPDATE tags SET owner_id = $1 WHERE name = $2 AND guild_id = $3"
                name = tag.name
            await ctx.db.execute(query, member.id, name, ctx.guild.id)

        await ctx.send(ctx.lang['transfered_tag_to'].format(member.mention))

    @tag.command()
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, member: discord.Member):
        query = "SELECT COUNT(*) FROM tags WHERE guild_id = $1 AND owner_id = $2;"
        count = await self.bot.db.fetchrow(query, ctx.guild.id, member.id)
        count = count[0]

        if count == 0:
            return await ctx.send(ctx.lang['member_no_tags'].format(str(member)))

        confirm = await ctx.confirm(ctx.lang['purge_tags_confirmation'].format(count, member), ctx.author)
        if not confirm:
            return await ctx.send(ctx.lang['abort'])

        query = "DELETE FROM tags WHERE guild_id = $1 AND owner_id = $2"
        await self.bot.db.execute(query, ctx.guild.id, member.id)

        await ctx.send(ctx.lang['purged_tags'].format(count, member.mention))

    @tag.command(aliases=['remove'])
    @commands.has_permissions(manage_messages=True)
    async def delete(self, ctx, *, name):
        tag = await self.get_tag(ctx.guild.id, name)
        alias = False

        if not tag:
            tag = await self.get_tag(ctx.guild.id, name, alias=True)
            alias = True
            if not tag:
                return await ctx.send(ctx.lang['tag_doesnt_exist'].format(clean_text(name)))

        confirm = await ctx.confirm(ctx.lang['delete_tag_confirmation'].format(clean_text(name)), ctx.author)
        if not confirm:
            return await ctx.send(ctx.lang['abort'])

        if not alias:
            name = tag.name
            query = "DELETE FROM tags WHERE guild_id = $1 AND lower(name) = $2;"
        else:
            name = tag.alias
            query = "DELETE FROM tags_lookup WHERE guild_id = $1 AND lower(alias) = $2"
        await self.bot.db.execute(query, ctx.guild.id, name.lower())

        member = ctx.guild.get_member(tag.owner_id) or await ctx.guild.fetch_member(tag.owner_id)

        await ctx.send(ctx.lang['deleted_tag'].format(clean_text(name), member.mention if member is not None else '**LEFT**'))

    @tag.command()
    async def search(self, ctx, *, query: commands.clean_content):
        if len(query) < 3:
            return await ctx.send(ctx.lang['too_short_query'])

        sql = """SELECT name
                 FROM tags
                 WHERE guild_id = $1 AND name % $2
                 ORDER BY similarity(name, $2) DESC
                 LIMIT 100;
              """

        results = await self.bot.db.fetch(sql, ctx.guild.id, query)

        if results:
            try:
                await ctx.paginate(entries=tuple(r[0] for r in results), per_page=20)
            except Exception as e:
                await ctx.send(e)
        else:
            await ctx.send(ctx.lang['nothing_found'])


def setup(bot):
    bot.add_cog(Tags(bot))
