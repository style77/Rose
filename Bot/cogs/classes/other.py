import argparse
import asyncio
import functools

import aiohttp
from discord.ext import commands

from concurrent.futures.thread import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from io import BytesIO
from PIL import Image


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


class SeleniumPhase:
    EXECUTOR = ThreadPoolExecutor(10)
    FIREFOX_DRIVER = "/assets/other/geckodriver"
    FIREFOX_BINARY = "/usr/bin/firefox"
    WINDOW_SIZE = "1920,1080"

    def __init__(self, bot):
        self.bot = bot
        self.loop = bot.loop

        self.driver = None

    def __scrape(self, url):
        self.driver.get(url)

    def _prepare_driver(self):
        cap = DesiredCapabilities().FIREFOX
        cap["marionette"] = True

        options = Options()
        options.headless = True
        options.binary = self.FIREFOX_BINARY

        self.driver = webdriver.Firefox(capabilities=cap, firefox_options=options, executable_path=self.FIREFOX_DRIVER)

    def _take_screenshot(self, url):
        if not self.driver:
            self._prepare_driver()

        self.__scrape(url)

        png = self.driver.get_screenshot_as_png()
        self.driver.close()

        im = Image.open(BytesIO(png))
        return im

    async def take_screenshot(self, url):
        func = functools.partial(self._take_screenshot, url)
        x = await self.bot.loop.run_in_executor(None, func)
        return x


class Plugin(commands.Cog):
    def __init__(self, bot, *, command_attrs=None):
        if command_attrs is None:
            command_attrs = {'not_turnable': False}
        self.bot = bot

        self.command_attrs = command_attrs

    def is_turnable(self):
        return not self.command_attrs['not_turnable']

    @property
    def name(self) -> str:
        return self.qualified_name

    def get_all_commands(self):

        commands_ = []

        for command in self.walk_commands():
            commands_.append(command)

        return commands_

    async def turn_off(self, guild_id):
        guild = await self.bot.get_guild_settings(guild_id)
        await guild.set_plugin(self, False)

    async def turn_on(self, guild_id):
        guild = await self.bot.get_guild_settings(guild_id)
        await guild.set_plugin(self, True)


async def get_avatar_bytes(avatar_url):
    session = aiohttp.ClientSession()

    async with session as s:
        async with s.get(avatar_url) as response:
            image_bytes = await response.read()
    return image_bytes


# ELO SYSTEM


def _expected(player, opponent):
    return (1 + 10 ** ((opponent.rating - player.rating) / 400.0)) ** -1


def match(player, opponent, winner):
    if winner == player:
        score1 = 1.0
        score2 = 0.0
    elif winner == opponent:
        score1 = 0.0
        score2 = 1.0
    else:
        score1 = 0.5
        score2 = 0.5

    k = 84

    new_rating1 = player.rating + k * (score1 - _expected(player, opponent))
    new_rating2 = opponent.rating + k * (score2 - _expected(opponent, player))

    if new_rating1 < 0:
        new_rating1 = 0
        new_rating2 = opponent.rating - player.rating

    elif new_rating2 < 0:
        new_rating2 = 0
        new_rating1 = player.rating - opponent.rating

    # player.rating = new_rating1
    # opponent.rating = new_rating2

    return new_rating1, new_rating2


# p1 = Player(123, "style", 1000)
# p2 = Player(124, "style2", 900)
#
# match(p1, p2)
#
# print(p1.rating)
# print(p2.rating)
