from . import dtab
import discord

async def get_settings(ctx, guild_id):
    guild = await ctx.bot.pg_con.fetchrow("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
    if guild:
        return Settings(guild)
    else: 
        return None

async def get_guild_settings(ctx, guild_id):
    guild = await ctx.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
    if guild:
        return guild[0]
    else: 
        return None

async def stars_count(ctx, guild_id):
    guild_settings = await get_guild_settings(ctx, guild_id)
    return guild_settings['stars_count']

async def get_starboard(ctx, guild_id):
    guild = await ctx.bot.pg_con.fetch("SELECT * FROM guild_settings WHERE guild_id = $1", guild_id)
    if guild:
        return guild[0]['heartboard']
    return None

def replace_with_args(text, member):
    if "<USER>" in text:
        text = text.replace("<USER>", member.name)
    if "<USER_DISCRIM>" in text:
        text = text.replace("<USER_DISCRIM>", str(member.discriminator))
    if "<@USER>" in text:
        text = text.replace("<@USER>", member.mention)
    if "<GUILD>" in text:
        text = text.replace("<GUILD>", member.guild.name)
    if "<GUILD_COUNT>" in text:
        text = text.replace("<GUILD_COUNT>", str(len(member.guild.members)-1))
    if "<GUILD_COUNT+>" in text:
        text = text.replace("<GUILD_COUNT+>", str(len(member.guild.members)))
    if "<GUILD_OWNER>" in text:
        text = text.replace("<GUILD_OWNER>", member.guild.owner)
    return text

class Settings:
    def __init__(self, guild):
        self.guild = guild

    @property
    def stars_count(self):
        return self.guild['stars_count']

    @property
    async def language(self):
        return self.guild['language']
