import colorsys
import random
from typing import Optional
from datetime import timedelta

import riotwatcher

from discord import Embed, Color, User
from discord.ext import commands
from fortnite_python import Fortnite
from fortnite_python.exceptions import NotFoundError

from fortnite_python.domain import Platform, Mode
from osuapi import OsuApi, AHConnector, OsuMode

from .utils import checks
from .utils import utils
from .classes.plugin import Plugin


class PlatformConverter(commands.Converter):
    async def convert(self, ctx, argument):
        if argument.lower() == "pc":
            return Platform.PC
        elif argument.lower() in ["ps4", "psn", "ps"]:
            return Platform.PSN
        elif argument.lower() in ["xbox", "xbl", "xb", "xbox360", "xb360", "xbl360"]:
            return Platform.XBOX
        else:
            return Platform.PC


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
        self.bot = bot

        self.fortnite = Fortnite(utils.get_from_config('fortnite_api'))
        self.watcher = riotwatcher.RiotWatcher(utils.get_from_config('riot_api'))
        self.osu = OsuApi(utils.get_from_config('osu_api'), connector=AHConnector())

    async def get_premium(self, user_id):
        member = await self.bot.pg_con.fetchrow("SELECT * FROM members WHERE id = $1", user_id)
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
        await self.bot.pg_con.execute(f"UPDATE members SET {game} = $1 WHERE id = $2", nick, user_id)

    @commands.group(alaises=['connect_account'], invoke_without_command=True)
    @checks.has_premium()
    async def link_account(self, ctx):
        """Podłącza konto danej gry do twojego konta premium."""
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")
        await ctx.send(_(ctx.lang, "Możesz ustawić:\n```\n{}```").format('\n'.join(z)))

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
    async def fortnite(self, ctx, platform: PlatformConverter = "PC", *, nick: str = None):
        """If your nickname is reserved by command name then add `reserved--` at start of your nick."""
        if not nick:
            nick = await self._get_connected_nick(ctx)

        nick = nick.replace('reserved--', '')

        try:
            player = self.fortnite.player(nick, platform)
        except NotFoundError:
            return await ctx.send(_("Nie znaleziono tej osoby. Sprawdź poprawność nazwy."))

        values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]

        solo = player.get_stats(Mode.SOLO)
        duo = player.get_stats(Mode.DUO)
        squad = player.get_stats(Mode.SQUAD)

        z = f"**SOLO**\nWins: {solo.top1}\nTop 3: {solo.top3}\nTop 5: {solo.top5}\nTop 10: {solo.top10}\n" \
            f"Kills: {solo.kills}\nKDA: {solo.kd}\n\n" \
            f"**DUO**\nWins: {duo.top1}\nTop 3: {duo.top3}\nTop 5: {duo.top5}\nTop 10: {duo.top10}\n" \
            f"Kills: {duo.kills}\nKDA: {duo.kd}\n\n" \
            f"**SQUAD**\nWins: {squad.top1}\nTop 3: {squad.top3}\nTop 5: {squad.top5}\nTop 10: {squad.top10}\n" \
            f"Kills: {squad.kills}\nKDA: {squad.kd}"

        e = Embed(description=z, color=Color.from_rgb(*values), timestamp=ctx.message.created_at)

        e.set_author(name=nick)

        await ctx.send(embed=e)

    # @fortnite.command(aliases=['shop'])
    # async def store(self, ctx):
    #     store = self.fortnite.store()

    # @commands.command(aliases=['lolstats'])
    # @commands.cooldown(1, 5, commands.BucketType.user)
    # async def lol_stats(self, ctx, region: RegionConverter = "eune", *, summoner: str):
    #     if not summoner:
    #         summoner = await self._get_connected_nick(ctx)
    #
    #     summoner = summoner.replace('reserved--', '')
    #     try:
    #         player = self.watcher.summoner.by_name(region, summoner)
    #     except riotwatcher.ApiError as err:
    #         if err.response.status_code == 404:
    #             return await ctx.send(_(ctx.lang, "Summoner z tą nazwą nie istnieje. Sprawdź swój region i nazwę."))
    #         else:
    #             return await ctx.send(f"```{err}```")
    #
    #     my_ranked_stats = self.watcher.league.positions_by_summoner(region, player['id'])
    #
    #     print(my_ranked_stats)
    #
    #     e = Embed()
    #     e.set_author(name=summoner)
    #
    #     await ctx.send(embed=e)

    @commands.group(invoke_without_command=True)
    async def osu(self, ctx, *, nick: str = None):
        if not nick:
            nick = await self._get_connected_nick(ctx)

        nick = nick.replace('reserved--', '')

        results = await self.osu.get_user(nick)
        if not results:
            return await ctx.send(_(ctx.lang, "Nie znaleziono tej osoby. Sprawdź poprawność nazwy."))

        z = f"**{_(ctx.lang, 'Czas gry')}**: {timedelta(seconds=results[0].total_seconds_played)}\n" \
            f"**Rank**: #{results[0].pp_rank} ({results[0].country}#{results[0].pp_country_rank})\n" \
            f"**PP**: {round(results[0].pp_raw)}\n" \
            f"**Level**: {round(results[0].level)}\n" \
            f"**Accuracy**: {round(results[0].accuracy)}%\n" \
            f"**{_(ctx.lang, 'Dołączył do osu!')}**: {results[0].join_date}\n" \
            f"**{_(ctx.lang, 'Ilość rozegranych map')}**: {results[0].playcount}\n"

        values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
        icon_url = f'https://a.ppy.sh/{results[0].user_id}'

        e = Embed(description=z, color=Color.from_rgb(*values))
        e.set_author(name=results[0].username, url=f"https://osu.ppy.sh/users/{results[0].user_id}", icon_url=icon_url)
        e.set_thumbnail(url=icon_url)
        e.set_footer(text="\U0001f339" + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))

        return await ctx.send(embed=e)

    @osu.command(aliases=['rs'])
    async def recent(self, ctx, nick: str = None):
        if not nick:
            nick = await self._get_connected_nick(ctx)

        nick = nick.replace('reserved--', '')

        results = await self.osu.get_user(nick)
        if not results:
            return await ctx.send(_(ctx.lang, "Nie znaleziono tej osoby. Sprawdź poprawność nazwy."))

        recent = await self.osu.get_user_recent(results[0].username)
        if not recent:
            return await ctx.send(_(ctx.lang, "Nie znaleziono niedawnych wyników dla **{}**.").format(results[0].username))

        s = await self.osu.get_scores(recent[0].beatmap_id, username=results[0].username, limit=100)
        score = None
        for score_ in s:
            if score_.date == recent[0].date:
                score = score_
                break

        if score is None:
            return await ctx.send(
                _(ctx.lang, "Nie znaleziono niedawnych wyników dla **{}**.").format(results[0].username))

        beatmap = await self.osu.get_beatmaps(beatmap_id=recent[0].beatmap_id)
        if not beatmap:
            return await ctx.send(_(ctx.lang, "Nie znaleziono niedawnych wyników dla **{}**.").format(results[0].username))

        values = [int(x * 255) for x in colorsys.hsv_to_rgb(random.random(), 1, 1)]
        icon_url = f'https://a.ppy.sh/{results[0].user_id}'

        z = f"**PP**: {round(score.pp)}\n" \
            f"**{_(ctx.lang, 'Wynik')}**: {recent[0].score}\n" \
            f"**Combo**: x{recent[0].maxcombo}\n" \
            f"**Misses**: {recent[0].countmiss}, " \
            f"**x50**: {recent[0].count50}, " \
            f"**x100**: {recent[0].count100}, " \
            f"**x300**: {recent[0].count300}"

        e = Embed(description=z, color=Color.from_rgb(*values), timestamp=recent[0].date)
        e.set_author(name=beatmap[0].title, url=f"https://osu.ppy.sh/b/{recent[0].beatmap_id}", icon_url=icon_url)
        # e.set_thumbnail(url=f"https://assets.ppy.sh/beatmaps/{recent[0].beatmap_id}/covers/cover.jpg")
        e.set_footer(text="\U0001f339" + _(ctx.lang, "Wykonane przez {}.").format(ctx.author.id))

        return await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(GameStats(bot))
