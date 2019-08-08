from discord.ext import commands

"""
They are not working for now, because i have to find a way to confirm if emote is not nsfw/gore.
"""

class Emotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def enabled(self, guild_id, thing, message):
        settings = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", str(guild_id))
        if not settings:
            return False
        if settings[0][thing] is True:
            return True
        return False
    """
    async def is_banned(self, guild_id, name):
        settings = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", str(guild_id))
        if not settings:
            return False
        elif not settings[0]['banned']:
            return False
        elif name in settings[0]['banned']:
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self,message):
        msg_search_for_emote = re.search(";;(.*);;", message.content.lower())
        if msg_search_for_emote:
            if await self.enabled(message.guild.id,'global_emojis',message):
                emoji_name=msg_search_for_emote.group(0).replace(";;","")
                if await self.is_banned(message.guild.id, emoji_name):
                    return
                emotes=await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
                if not emotes:
                    return
                await self.bot.pg_con.execute("UPDATE emotes SET emoji_uses = $1 WHERE emoji_name = $2",int(emotes[0]['emoji_uses'])+1,str(emoji_name))
                await message.channel.send(emotes[0]['emoji'])
            else:
                return

    @commands.command()
    async def emotes(self, ctx, member: typing.Optional[discord.Member]=None):
        emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes")
        if member:
             emotes=await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_author_id = $1",str(member.id))
        entries = [f"{t['emoji']} - {t['emoji_name']}" for t in emotes]
        if len(entries) < 1:
            return await ctx.send('Nie posiadam żadnych emotek w bazie danych.') #not possible
        pages = utils.Pages(ctx, entries=entries)
        await pages.paginate()

    @commands.group(invoke_without_command=True)
    async def emote(self,ctx):
        await ctx.send('```\n- add\n- remove\n- info\n- gimme```')

    @emote.command()
    async def react(self, ctx, message_id: int=None, emoji_name: str=None):
        if not message_id or not emoji_name:
            return await ctx.send(f'Użycie `{ctx.prefix}emote react message_id emoji_name`')
        emoji_name = emoji_name.replace(";;","")
        emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
        if not emotes:
            return await ctx.send('Nie ma takiej emotki.')
        await self.bot.pg_con.execute("UPDATE emotes SET emoji_uses = $1 WHERE emoji_name = $2",int(emotes[0]['emoji_uses'])+1,str(emoji_name))
        ms = await ctx.channel.fetch_message(int(message_id))
        await ms.add_reaction(str(emotes[0]['emoji']).replace(">",""))

    @emote.command()
    @commands.has_permissions(manage_emojis=True)
    async def add(self, ctx, emoji_name, emoji_content: commands.EmojiConverter):
        if await self.enabled(ctx.guild.id,'global_emojis',ctx):
            emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
            if not emotes:
                await self.bot.pg_con.execute("INSERT INTO emotes (emoji_name, emoji, emoji_author_id, emoji_created, emoji_from, emoji_uses) VALUES ($1,$2,$3,$4,$5, 0)",str(emoji_name),str(emoji_content),str(ctx.author.id),str(ctx.message.created_at),str(ctx.guild.id))
                await ctx.send(f'Dodano **{emoji_name}** z {emoji_content}')
            if emotes:
                return await ctx.send(f'Emotka o nazwie `{emoji_name}` już istnieje.')

    #@add.error
    #async def add_handler(self,ctx,error):
        #if isinstance(error, commands.BadArgument):
            #return await ctx.send('Nie możesz używać emotek unicode.')

    @emote.command()
    async def remove(self, ctx, emoji_name):
        emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
        if ctx.author.id == int(emotes[0]['emoji_author_id']) or ctx.author.id == 185712375628824577:
            if emotes:
                await self.bot.pg_con.execute("DELETE FROM emotes WHERE emoji_name = $1",str(emoji_name))
                await ctx.send(f'Usunięto **{emoji_name}**')
            if not emotes:
                return await ctx.send(f'Emotka o nazwie **{emoji_name}** nie istnieje.')
        else:
            return await ctx.send(f'Nie posiadasz uprawnień do usuwania globalnych emotek, ani nie jesteś jej włascicielem.')

    @emote.command()
    async def info(self,ctx,emoji_name):
        emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
        if not emotes:
            return await ctx.send(f'**{emoji_name}** nie istnieje.')
        author = self.bot.get_user(int(emotes[0]['emoji_author_id']))
        made = datetime.datetime.strptime(emotes[0]['emoji_created'],'%Y-%m-%d %H:%M:%S.%f')
        e = discord.Embed(description=f"{emotes[0]['emoji']}\nAutor: **{author}**\nUżycia: **{emotes[0]['emoji_uses']}**\nStworzony na: **{self.bot.get_guild(int(emotes[0]['emoji_from'])).name}**", color=0xEC3B8E, timestamp=made)
        e.set_author(name=emotes[0]['emoji_name'],icon_url=author.avatar_url)
        await ctx.send(embed=e)

    @emote.command()
    async def gimme(self,ctx,emoji_name):
        if await self.enabled(ctx.guild.id, 'global_emojis', ctx):
            if emoji_name.startswith(";;") and emoji_name.endswith(";;"):
                emoji_name = emoji_name.replace(";;","")
            emotes = await self.bot.pg_con.fetch("SELECT * FROM emotes WHERE emoji_name = $1",str(emoji_name))
            if not emotes:
                return await ctx.send('Nie znalazłem tej emotki.')
            await self.bot.pg_con.execute("UPDATE emotes SET emoji_uses = $1 WHERE emoji_name = $2",emotes[0]['emoji_uses']+1,str(emoji_name))
            await ctx.message.add_reaction("📨")
            await ctx.author.send(emotes[0]['emoji'])
        else:
            return await ctx.send('Globalne emotki są wyłączone')
"""

def setup(bot):
    bot.add_cog(Emotes(bot))
