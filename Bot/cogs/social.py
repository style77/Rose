import json

import discord
from discord.ext import commands

from .utils import fuzzy, get_language
from .classes.other import Plugin


class Social(Plugin):
    def __init__(self, bot):
        super().__init__(bot, command_attrs={'not_turnable': True})
        self.bot = bot

        self.faq_entries = None

    @commands.command()
    async def support(self, ctx):
        # await ctx.send(f"{ctx.lang['join_us']} discord.gg/{self.bot._config['support']}")
        await ctx.send(f"discord.gg/{self.bot._config['support']}")

    @commands.command(aliases=['add', 'addbot', 'add_bot'])
    async def invite(self, ctx):
        msg = await ctx.send(discord.utils.oauth_url(self.bot.user.id, permissions=discord.Permissions(8)))
        try:
            await msg.add_reaction("\U00002764")
        except discord.HTTPException:
            pass

    def refresh_entries(self):
        with open('assets/other/faq.json', 'r') as f:
            data = json.load(f)

            self.faq_entries = {}

            self.faq_entries['pl'] = data['pl']
            self.faq_entries['eng'] = data['eng']

    @commands.command()
    async def faq(self, ctx, *, query: str):
        if not self.faq_entries:
            self.refresh_entries()

        lang = await get_language(self.bot, ctx.guild)
        faq = self.faq_entries[lang.lower()]

        matches = fuzzy.extract_matches(query, faq, scorer=fuzzy.partial_ratio, score_cutoff=40)
        if len(matches) == 0:
            return await ctx.send(ctx.lang['nothing_found'])

        paginator = commands.Paginator(suffix='', prefix='')
        for key, _, value in matches:
            paginator.add_line(f'**{key}**\n{value}')
        page = paginator.pages[0]
        await ctx.send(page)

    @commands.command()
    @commands.is_owner()
    async def refresh_faq(self, ctx):
        self.refresh_entries()
        await ctx.send(':ok_hand:')

    @commands.command()
    async def top_popular(self, ctx):
        async with self.bot.session.get("https://botpanel.pl/api/web/dbl/572906387382861835") as r:
            data = await r.json()

        need = data['server_count'] - len(self.bot.guilds)

        await ctx.send(ctx.lang['need_to_beat'].format(need))

    @commands.command()
    async def donate(self, ctx):
        """❤"""
        owner = str(self.bot.get_user(self.bot.owner_id))
        return await ctx.send(ctx.lang['donate'].format(owner))

def setup(bot):
    bot.add_cog(Social(bot))
