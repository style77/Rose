import discord
from discord.ext import commands

from .classes.plugin import Plugin
from .utils import settings

#Its heartboard but some variables are named "star" why? Because i've got idea to make heartboard when i finished starboard and i didnt want to broke code again, so i just changed visual things :).

class Stars(Plugin):
    def __init__(self, bot):
        self.bot = bot
        self.emotka = "❤"

    async def enabled(self, guild_id, thing):
        settings = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
        if settings[0][thing] == True:
            return True
        return False

    async def star_message(self, channel_id, guild_id, message_id, bot_message_id, author_id):
        await self.bot.pg_con.execute("INSERT INTO stars (author_id, guild_id, message_id, bot_message_id, channel_id, reactions) VALUES ($1, $2, $3, $4, $5, $6)", author_id, guild_id, message_id, bot_message_id, channel_id, [author_id])

    def star_gradient_colour(self, stars):
        if stars < 5:
            color = 0xf4b7cd
        elif stars < 10:
            color = 0xef9ebb
        elif stars < 15:
            color = 0xef88ad
        elif stars < 20:
            color = 0xed6a99
        elif stars >= 20:
            color = 0xea447f

        return color

    def get_emoji(self, stars):
        if stars < 3:
            emoji = self.emotka
        elif stars < 5:
            emoji = "💗"
        elif stars < 8:
            emoji = "💝"
        elif stars < 13:
            emoji = "💕"
        elif stars < 15:
            emoji = "💞"
        elif stars > 15:
            emoji = "💖"
        return emoji

    async def get_starboard(self, guild_id):
        option = await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
        if option:
            channel = option[0]['heartboard']
            return channel
        else:
            return

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def r_heartboard(self, ctx, chan_delete='false'):
        """Usuń heartboarda."""
        starboard = await settings.get_starboard(ctx, ctx.guild.id)
        if str(chan_delete).lower() not in ['false', 'true']:
            return await ctx.send(_(ctx.lang, "Użycie `{}r_heartboard {True/False}`.").format(ctx.prefix))
        if starboard:
            await self.bot.pg_con.execute("DELETE FROM guild_settings WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(':ok_hand:')
            if chan_delete.lower() == "true":
                channel = ctx.guild.get_channel(starboard)
                await channel.delete(reason="💔")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def heartboard(self, ctx, *, channel: discord.TextChannel=None):
        starboard = await settings.get_starboard(ctx, ctx.guild.id)
        try:
            if starboard:
                starboard = starboard
                s = ctx.guild.get_channel(starboard)
                return await ctx.send(_(ctx.lang, "Ten serwer już posiada heartboarda - {}.").format(s.mention))
            elif not channel:
                channel = await ctx.guild.create_text_channel("heartboard")
            if not await self.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", ctx.guild.id):
                await self.bot.pg_con.execute("INSERT INTO guild_settings (heartboard, guild_id) VALUES ($1, $2)", channel.id, ctx.guild.id)
            else:
                await self.bot.pg_con.execute("UPDATE guild_settings SET heartboard = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            await ctx.send(_(ctx.lang, ":ok_hand:\nPamietaj, jeśli będziesz chciał usunać heartboarda musisz najpierw wymazać go z bazy danych, tzn. użyc komendy `r_heartboard` i dopiero wtedy usunać kanał."))
        except Exception:
            await ctx.invoke(self.bot.get_command('r_heartboard'))
            await ctx.send(_(ctx.lang, "Coś poszło nie tak. Spróbuj ponownie."))

    async def update_star(self, bot_message_id, channel_id, guild_id, message_id, reactions, color, starboard):
        msg = await self.bot.get_guild(int(guild_id)).get_channel(int(channel_id)).fetch_message(int(message_id))
        e = discord.Embed(description=f"{msg.content}\n" if msg.content else None, color=color, timestamp=msg.created_at)
        if msg.attachments:
            e.set_image(url=msg.attachments[0].url)
        elif msg.embeds:
            e.set_image(url=msg.embeds[0].image.url)
        e.set_author(name=msg.author.name, icon_url=msg.author.avatar_url)
        bot_message_chan = self.bot.get_guild(int(guild_id)).get_channel(starboard)
        bot_message = await bot_message_chan.fetch_message(int(bot_message_id))
        await bot_message.edit(content=f"{self.get_emoji(reactions)} **{reactions}** {self.bot.get_guild(int(guild_id)).get_channel(int(channel_id)).mention} ID: {msg.id}",embed=e)

    async def remove_star(self, guild_id, message_id):
        star = await self.bot.pg_con.fetchrow("SELECT * FROM stars WHERE guild_id = $1 AND message_id = $2", guild_id, message_id)
        if star:
            channel = self.bot.get_channel(await settings.get_starboard(self, guild_id))
            message = await channel.fetch_message(star['bot_message_id'])
            await message.delete()
            return await self.bot.pg_con.execute("DELETE FROM stars WHERE guild_id = $1 AND message_id = $2", guild_id, message_id)
        return None

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        if payload.emoji.name == self.emotka:
            if payload.user_id == self.bot.user.id:
                return
            starboard = await settings.get_starboard(self, payload.guild_id)
            if starboard:
                star = await self.bot.pg_con.fetch("SELECT * FROM stars WHERE message_id = $1 or bot_message_id = $1", payload.message_id)
                if payload.user_id not in star[0]['reactions']:
                    return
                color = self.star_gradient_colour(len(star[0]['reactions']))
                if star:
                    star[0]['reactions'].remove(payload.user_id)
                    if len(star[0]['reactions']) < await settings.stars_count(self, payload.guild_id):
                        return await self.remove_star(payload.guild_id, star[0]['message_id'])
                    await self.bot.pg_con.execute("UPDATE stars SET reactions = $1 WHERE message_id = $2 or bot_message_id = $2", star[0]['reactions'], payload.message_id)
                    await self.update_star(star[0]['bot_message_id'], star[0]['channel_id'], payload.guild_id, star[0]['message_id'], len(star[0]['reactions']), color, starboard)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.emoji.name == self.emotka:
            if payload.user_id == self.bot.user.id:
                return
            starboard = await settings.get_starboard(self, payload.guild_id)
            if starboard:
                star = await self.bot.pg_con.fetch("SELECT * FROM stars WHERE message_id = $1 or bot_message_id = $1", payload.message_id)
                if star:
                    if payload.user_id in star[0]['reactions']:
                        return
                    star[0]['reactions'].append(payload.user_id)
                    await self.bot.pg_con.execute("UPDATE stars SET reactions = $1 WHERE message_id = $2 or bot_message_id = $2", star[0]['reactions'], payload.message_id)
                    color = self.star_gradient_colour(len(star[0]['reactions']))
                    await self.update_star(star[0]['bot_message_id'], star[0]['channel_id'], payload.guild_id, star[0]['message_id'], len(star[0]['reactions']), color, starboard)
                else:
                    msg = await self.bot.get_guild(payload.guild_id).get_channel(payload.channel_id).fetch_message(payload.message_id)
                    i = 0
                    for reaction in msg.reactions:
                        if reaction.emoji == self.emotka:
                            i += 1
                    if i >= await settings.stars_count(self, payload.guild_id):
                        if not await self.enabled(payload.guild_id, 'self_starring'):
                            if payload.user_id == msg.author.id:
                                return
                        e = discord.Embed(description=f"{msg.content}\n" if msg.content else None, color=self.star_gradient_colour(1), timestamp=msg.created_at)
                        if msg.attachments:
                            e.set_image(url=msg.attachments[0].url)
                        elif msg.embeds:
                            e.set_image(url=msg.embeds[0].image.url)
                        e.set_author(name=msg.author.name, icon_url=msg.author.avatar_url)
                        starboard = self.bot.get_channel(starboard)
                        bot_message = await starboard.send(content=f"{self.get_emoji(i)} **1** {self.bot.get_guild(payload.guild_id).get_channel(payload.channel_id).mention} ID: {msg.id}", embed=e)
                        await bot_message.add_reaction(self.emotka)
                        await self.star_message(payload.channel_id, payload.guild_id, payload.message_id, bot_message.id, payload.user_id)

    @commands.command()
    async def show(self, ctx, id):
        star = await self.bot.pg_con.fetch("SELECT * FROM stars WHERE guild_id = $1 AND message_id = $2 or bot_message_id = $2", int(ctx.guild.id), int(id))
        if star:
            channel = self.bot.get_channel(star[0]['channel_id'])
            msg = await channel.fetch_message(star[0]['message_id'])
            author = await self.bot.fetch_user(star[0]['author_id'])

            gradient = self.star_gradient_colour(len(star[0]['reactions']))
            embed = discord.Embed(
                description=_(ctx.lang, "Autor: **{}**\nwiadomosć: **{}**\nkanał: {}\nliczba serc: **{}**\nlink: **[JUMP TO](https://discordapp.com/channels/{}/{}/{})**").format(author, msg.content if msg.content else 'brak', channel.mention, len(star[0]['reactions']), ctx.guild.id, channel.id, msg.id), color=gradient, timestamp=msg.created_at)
            if msg.attachments:
                embed.set_image(url=msg.attachments[0].url)
            elif msg.embeds:
                embed.set_image(url=msg.embeds[0].image.url)
            embed.set_footer(text=author.name, icon_url=author.avatar_url)
            await ctx.send(embed=embed)
        elif not star:
            return await ctx.send(_(ctx.lang, "Nie znalazłem podanej wiadomości."))

def setup(bot):
    bot.add_cog(Stars(bot))
