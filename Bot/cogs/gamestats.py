import tabulate
from discord import Embed
from discord.ext import commands

from datetime import timedelta

from pantheon.pantheon import Pantheon

import pynite

from osuapi import OsuApi, AHConnector, OsuMode
import typing

from .classes.other import Plugin
from .utils import get, checks


class PlatformConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.lower() == "pc":
            return 'pc'
        elif argument.lower() in ["ps4", "psn", "ps"]:
            return 'psn'
        elif argument.lower() in ["xbox", "xbl", "xb", "xbox360", "xb360", "xbl360"]:
            return 'xbl'
        else:
            return 'pc'


class RegionConverter(commands.Converter):
    async def convert(self, ctx, argument) -> str:
        if argument.lower() in ["kr", "ru"]:
            return argument.lower()
        elif argument.lower() == "jp":
            return 'jp1'
        elif argument.lower() == "euw":
            return "euw1"
        elif argument.lower() == "eune":
            return "eun1"
        elif argument.lower() == "br":
            return "br1"
        elif argument.lower() == "lan":
            return "la1"
        elif argument.lower() == "las":
            return "la2"
        elif argument.lower() == "pbe":
            return "pbe1"
        elif argument.lower() == "tr":
            return "tr1"
        elif argument.lower() == "oce":
            return "oc1"

        # The NA region has two associated platform values - NA and NA1.
        # Older summoners will have the NA platform associated with their account,
        # while newer summoners will have the NA1 platform associated with their account.
        # via riot api docs

        # todo auto check if person is in na or na1

        elif argument.lower() == "na":
            return "na"
        elif argument.lower() == "na1":
            return "na1"

        else:
            return "eun1"


class GameStats(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

        self.riot_key = get('riot_api')

        self.fortnite = pynite.Client(get('fortnite_api'), timeout=5)
        self.osu = OsuApi(get('osu_api'), connector=AHConnector())

    async def get_premium(self, user_id):
        member = await self.bot.db.fetchrow("SELECT * FROM members WHERE id = $1", user_id)
        if member:
            return member
        return None

    async def _get_connected_nick(self, ctx):
        user = await self.get_premium(ctx.author.id)
        if user:
            stats_map = {
                'lol_stats': 'lol_nick',
                'osu': 'osu_nick',
                'recent': 'osu_nick',
                'fortnite': 'fortnite_nick'
            }
            nick = user[stats_map[ctx.command.name]]
        else:
            raise commands.UserInputError

        if nick is None:
            raise commands.UserInputError
        return nick

    async def _update_nick(self, user_id, game, nick):
        await self.bot.db.execute(f"UPDATE members SET {game} = $1 WHERE id = $2", nick, user_id)

    @commands.group(alaises=['connect_account'], invoke_without_command=True)
    @checks.has_premium()
    async def link_account(self, ctx):
        """Podłącza konto danej gry do twojego konta premium."""
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")
        await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @link_account.command(name="fortnite")
    @checks.has_premium()
    async def fortnite_(self, ctx, nick: str):
        await self._update_nick(ctx.author.id, 'fortnite_nick', nick)
        return await ctx.send(":ok_hand:")

    @link_account.command(name="osu")
    @checks.has_premium()
    async def osu_(self, ctx, nick: str):
        await self._update_nick(ctx.author.id, 'osu_nick', nick)
        return await ctx.send(":ok_hand:")

    @link_account.command(name="lol")
    @checks.has_premium()
    async def lol_stats_(self, ctx, nick: str):
        await self._update_nick(ctx.author.id, 'lol_nick', nick)
        return await ctx.send(":ok_hand:")

    @commands.group(invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def fortnite(self, ctx, platform: typing.Optional[PlatformConverter] = "pc", *, nick: str = None):
        if not nick:
            nick = await self._get_connected_nick(ctx)

        try:
            player = await self.fortnite.get_player(platform, nick)
        except (pynite.NotFound, pynite.NotResponding):
            return await ctx.send(ctx.lang['person_not_found'].format(nick))

        solo = await player.get_solos()
        duo = await player.get_duos()
        squad = await player.get_squads()
        # life = player.get_lifetime_stats()

        z = f"**SOLO**\nWins: {solo.top1.value}\nTop 3: {solo.top3.value}\nTop 5: {solo.top5.value}\nTop 10: {solo.top10.value}\n" \
            f"Kills: {solo.kills.value}\nKDA: {solo.kd.value}\n\n" \
            f"**DUO**\nWins: {duo.top1.value}\nTop 3: {duo.top3.value}\nTop 5: {duo.top5.value}\nTop 10: {duo.top10.value}\n" \
            f"Kills: {duo.kills.value}\nKDA: {duo.kd.value}\n\n" \
            f"**SQUAD**\nWins: {squad.top1.value}\nTop 3: {squad.top3.value}\nTop 5: {squad.top5.value}\nTop 10: {squad.top10.value}\n" \
            f"Kills: {squad.kills.value}\nKDA: {squad.kd.value}"

        # f = \
        # f"""
        # **SOLO**    **DUO**    **SQUAD**
        # Wins:{solo.top1.value}Wins:{duo.top1.value}\tWins:{squad.top1.value}
        # Top 3:{solo.top3.value}\tTop 3:{duo.top3.value}\tTop 3:{squad.top3.value}
        # Top 5:{solo.top5.value}\tTop 5:{duo.top5.value}\tTop 5:{squad.top5.value}
        # Top 10:{solo.top10.value}\tTop 10:{duo.top10.value}\tTop 10:{squad.top10.value}
        # Kills:{solo.kills.value}\tKills:{duo.kills.value}\tKills:{squad.kills.value}
        # KDA:{solo.kd.value}\tKDA:{duo.kd.value}\tKDA:{squad.kd.value}
        # """
        #
        # general_data = ['top1', 'top3', 'top5', 'top10', 'kills', 'kd']
        #
        # table = [['Wins', solo.top1.value], ['Top 3', solo.top3.value], ['Top 5', solo.top5.value],
        #          ['Top 10', solo.top10.value], ['Kills', solo.kills.value], ['KDA', solo.kd.value],
        #
        #          ['Wins', duo.top1.value], ['Top 3', duo.top3.value], ['Top 5', duo.top5.value],
        #          ['Top 10', duo.top10.value], ['Kills', duo.kills.value], ['KDA', duo.kd.value],
        #
        #          ['Wins', squad.top1.value], ['Top 3', squad.top3.value], ['Top 5', squad.top5.value],
        #          ['Top 10', squad.top10.value], ['Kills', squad.kills.value], ['KDA', squad.kd.value]]
        #
        # headers = ['solo', 'duo', 'squad']
        #
        # z2 = tabulate.tabulate(table, headers)

        e = Embed(description=z, color=self.bot.color, timestamp=ctx.message.created_at)

        e.set_author(name=nick, icon_url=ctx.author.avatar_url)

        await ctx.send(embed=e)

    # @fortnite.command(aliases=['shop'])
    # async def store(self, ctx):
    #     store = self.fortnite.store()

    # @staticmethod
    # async def getRecentMatchlist(panth, accountId):
    #     try:
    #         data = await panth.getMatchlist(accountId, params={"endIndex": 10})
    #         return data
    #     except:
    #         raise
    #
    # @commands.command(aliases=['lolstats'])
    # @commands.cooldown(1, 5, commands.BucketType.user)
    # async def lol_stats(self, ctx, region: RegionConverter = "eune", *, summoner: str):
    #     if not summoner:
    #         summoner = await self._get_connected_nick(ctx)
    #
    #     pantheon = Pantheon(region, self.riot_key)
    #
    #     try:
    #         player = await pantheon.getSummonerByName(summoner)
    #         print(player)
    #     except Exception as e:
    #         # if err.response.status_code == 404:
    #         #     return await ctx.send(_(ctx.lang, "Summoner z tą nazwą nie istnieje. Sprawdź swój region i nazwę."))
    #         # else:
    #         return await ctx.send(f"```{e}```")
    #
    #     recent = await self.getRecentMatchlist(pantheon, player['accountId'])
    #
    #     print(recent)
    #
    #     e = Embed()
    #     e.set_author(name=summoner)
    #
    #     await ctx.send(embed=e)

    @commands.group(invoke_without_command=True)
    async def osu(self, ctx, *, nick: str = None):
        if not nick:
            nick = await self._get_connected_nick(ctx)

        results = await self.osu.get_user(nick)
        if not results:
            return await ctx.send(ctx.lang['person_not_found'].format(nick))

        z = f"**{ctx.lang['play_time']}**: {timedelta(seconds=results[0].total_seconds_played)}\n" \
            f"**Rank**: #{results[0].pp_rank} ({results[0].country}#{results[0].pp_country_rank})\n" \
            f"**PP**: {round(results[0].pp_raw)}\n" \
            f"**Level**: {round(results[0].level)}\n" \
            f"**Accuracy**: {round(results[0].accuracy)}%\n" \
            f"**{ctx.lang['joined_osu']}**: {results[0].join_date}\n" \
            f"**{ctx.lang['play_count']}**: {results[0].playcount}\n"

        icon_url = f'https://a.ppy.sh/{results[0].user_id}'

        e = Embed(description=z, color=self.bot.color)
        e.set_author(name=results[0].username, url=f"https://osu.ppy.sh/users/{results[0].user_id}", icon_url=icon_url)
        e.set_thumbnail(url=icon_url)
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")

        return await ctx.send(embed=e)

    @osu.command(aliases=['rs'])
    async def recent(self, ctx, *, nick: str = None):
        if not nick:
            nick = await self._get_connected_nick(ctx)

        results = await self.osu.get_user(nick)
        if not results:
            return await ctx.send(ctx.lang['person_not_found'].format(nick))

        recent = await self.osu.get_user_recent(results[0].username)
        if not recent:
            return await ctx.send(ctx.lang['not_found_recent'].format(results[0].username))

        s = await self.osu.get_scores(recent[0].beatmap_id, username=results[0].username, limit=100)
        score = None
        for score_ in s:
            if score_.date == recent[0].date:
                score = score_
                break

        if score is None:
            return await ctx.send(ctx.lang['not_found_recent'].format(results[0].username))

        beatmap = await self.osu.get_beatmaps(beatmap_id=recent[0].beatmap_id)
        if not beatmap:
            return await ctx.send(ctx.lang['not_found_recent'].format(results[0].username))

        icon_url = f'https://a.ppy.sh/{results[0].user_id}'

        z = f"**PP**: {round(score.pp)}\n" \
            f"**{ctx.lang['score']}**: {recent[0].score}\n" \
            f"**Combo**: x{recent[0].maxcombo}\n" \
            f"**Misses**: {recent[0].countmiss}, " \
            f"**x50**: {recent[0].count50}, " \
            f"**x100**: {recent[0].count100}, " \
            f"**x300**: {recent[0].count300}"

        e = Embed(description=z, color=self.bot.color, timestamp=recent[0].date)
        e.set_author(name=beatmap[0].title, url=f"https://osu.ppy.sh/b/{recent[0].beatmap_id}", icon_url=icon_url)
        # e.set_thumbnail(url=f"https://assets.ppy.sh/beatmaps/{recent[0].beatmap_id}/covers/cover.jpg")
        e.set_footer(text=f"\U0001f339 {ctx.lang['done_by']} {ctx.author.id}.")

        return await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(GameStats(bot))
