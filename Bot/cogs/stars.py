import discord
from discord.ext import commands

from .classes.other import Plugin


class Stars(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def cog_check(self, ctx):
        return ctx.guild is not None

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):  # todo custom shade
        guild = await self.bot.get_guild_settings(payload.guild_id)

        starboard = guild.get_starboard()

        if not starboard:
            return

        if self.bot.get_user(payload.user_id).bot:
            return

        emoji = guild.stars['emoji']

        if emoji == str(payload.emoji) or emoji == payload.emoji.name:

            color = int(guild.stars['color'], 16)

            star = await self.bot.db.fetchrow("SELECT * FROM stars WHERE message_id = $1 or bot_message_id = $1",
                                              payload.message_id)

            if star:
                if payload.user_id in star['reactions']:
                    return

                star['reactions'].append(payload.user_id)

                await self.bot.db.execute(
                    "UPDATE stars SET reactions = $1 WHERE message_id = $2 or bot_message_id = $2",
                    star['reactions'], payload.message_id)

                await self.update_star(star['bot_message_id'], star['channel_id'], payload.guild_id,
                                       star['message_id'], len(star['reactions']), color, emoji)

            else:
                if payload.user_id == self.bot.user.id:
                    return

                msg = discord.utils.get(self.bot.cached_messages, id=payload.message_id)
                if not msg:
                    channel = self.bot.get_channel(payload.channel_id)
                    msg = await channel.fetch_message(payload.message_id)

                if not guild.stars['self_starring'] and payload.user_id == msg.author.id:
                    return

                reactions = [reaction for reaction in msg.reactions if str(reaction.emoji) == emoji or reaction.emoji.name == emoji]
                reactions = len(reactions)

                if reactions >= guild.stars['stars_count']:

                    e = discord.Embed(description=f"{msg.content}\n" if msg.content else None, color=color,
                                      timestamp=msg.created_at)

                    if msg.attachments:
                        e.set_image(url=msg.attachments[0].url)
                    elif msg.embeds:
                        e.set_image(url=msg.embeds[0].image.url)

                    e.set_author(name=msg.author.name, icon_url=msg.author.avatar_url)

                    bot_message = await starboard.send(content=f"{emoji} **1** {msg.channel.mention} ID: {msg.id}",
                                                       embed=e)
                    print('sended')
                    await bot_message.add_reaction(payload.emoji)

                    print('added reraction')

                    await self.bot.db.execute(
                        "INSERT INTO stars (author_id, guild_id, message_id, bot_message_id, channel_id, reactions) VALUES "
                        "($1, $2, $3, $4, $5, $6)",
                        payload.user_id, payload.guild_id, payload.message_id, bot_message.id, payload.channel_id,
                        [payload.user_id])

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        guild = await self.bot.get_guild_settings(payload.guild_id)

        starboard = guild.get_starboard()

        if not starboard:
            return

        if self.bot.get_user(payload.user_id).bot:
            return

        emoji = guild.stars['emoji']

        if payload.emoji.name == emoji or str(payload.emoji) == emoji:
            star = await self.bot.db.fetchrow("SELECT * FROM stars WHERE message_id = $1 or bot_message_id = $1",
                                              payload.message_id)
            if not star:
                return

            if payload.user_id not in star['reactions']:  # should not be possible but...
                return

            color = int(guild.stars['color'], 16)

            star['reactions'].remove(payload.user_id)

            if len(star['reactions']) < guild.stars['stars_count']:
                return await self.remove_star(payload.guild_id, star['message_id'])

            await self.bot.db.execute(
                "UPDATE stars SET reactions = $1 WHERE message_id = $2 or bot_message_id = $2", star['reactions'],
                payload.message_id)

            await self.update_star(star['bot_message_id'], star['channel_id'], payload.guild_id,
                                   star['message_id'], len(star['reactions']), color, emoji)

    async def update_star(self, bot_message_id, channel_id, guild_id, message_id, reactions_count, color, emoji):
        msg = await self.bot.get_channel(channel_id).fetch_message(message_id)

        e = discord.Embed(description=f"{msg.content}\n" if msg.content else None, color=color, timestamp=msg.created_at)

        if msg.attachments:
            e.set_image(url=msg.attachments[0].url)
        elif msg.embeds:
            e.set_image(url=msg.embeds[0].image.url)

        e.set_author(name=msg.author.name, icon_url=msg.author.avatar_url)

        guild = await self.bot.get_guild_settings(guild_id)
        starboard = guild.get_starboard()

        bot_message = await starboard.fetch_message(bot_message_id)

        await bot_message.edit(content=f"{emoji} **{reactions_count}** "
                                       f"{self.bot.get_guild(guild_id).get_channel(channel_id).mention} ID: {msg.id}",
                               embed=e)

    async def remove_star(self, guild_id, message_id):
        guild_settings = await self.bot.get_guild_settings(guild_id)
        star = await self.bot.db.fetchrow("SELECT * FROM stars WHERE guild_id = $1 AND message_id = $2", guild_id,
                                          message_id)
        if star:
            message = discord.utils.get(self.bot.cached_messages, id=star['bot_message_id'])
            if not message:
                starboard = guild_settings.get_starboard()
                message = await starboard.fetch_message(star['bot_message_id'])

            await message.delete()
            await self.bot.db.execute("DELETE FROM stars WHERE guild_id = $1 AND message_id = $2", guild_id,
                                      message_id)

    @commands.command()
    async def show(self, ctx, message: discord.Message):
        """Pokazuje szczegółowe informacje o wiadomości z heartboarda."""

        query = "SELECT * FROM stars WHERE guild_id = $1 AND message_id = $2 OR bot_message_id = $2"
        star = await self.bot.db.fetchrow(query, ctx.guild.id, message.id)

        if star:
            channel = self.bot.get_channel(star['channel_id'])
            msg = await channel.fetch_message(star['message_id'])
            author = await self.bot.fetch_user(star['author_id'])

            guild = await self.bot.get_guild_settings(ctx.guild.id)

            color = int(guild.stars['color'], 16)

            embed = discord.Embed(
                description=ctx.lang['star_info'].format(author, msg.content if msg.content else 'none',
                                                         channel.mention, len(star['reactions']), ctx.guild.id,
                                                         channel.id, msg.id), color=color, timestamp=msg.created_at)

            if msg.attachments:
                embed.set_image(url=msg.attachments[0].url)
            elif msg.embeds:
                embed.set_image(url=msg.embeds[0].image.url)

            embed.set_footer(text=author.name, icon_url=author.avatar_url)

            await ctx.send(embed=embed)

        else:
            return await ctx.send(ctx.lang['not_found'])


def setup(bot):
    bot.add_cog(Stars(bot))
