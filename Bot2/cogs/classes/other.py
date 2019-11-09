import functools

from discord.ext import commands

from concurrent.futures.thread import ThreadPoolExecutor

from selenium import webdriver
from selenium.webdriver.firefox.options import Options

from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from io import BytesIO
from PIL import Image


class SeleniumPhase:
    EXECUTOR = ThreadPoolExecutor(10)
    FIREFOX_DRIVER = "/home/style/PycharmProjects/Rosie/Bot2/assets/other/geckodriver"
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
            command_attrs = dict()
        self.bot = bot

        self.command_attrs = command_attrs

    def is_turnable(self):
        return not self.command_attrs['not_turnable']

    @property
    def name(self):
        return self.qualified_name

    def get_all_commands(self):

        commands_ = []

        for command in self.walk_commands():
            commands_.append(command)

        return commands_

    async def set_plugin(self, db, guild_id, on=True):
        if not self.is_turnable():
            raise commands.BadArgument(f"{self.qualified_name} is not possible to turn off/on")

        plugins = await db.fetchrow("SELECT plugins_off FROM guild_settings WHERE guild_id = $1", guild_id)
        if on is False:
            if self.name in plugins[0]:
                raise commands.BadArgument("This plugin is already on.")
            plugins[0].append(self.name)
        else:
            if self.name not in plugins[0]:
                raise commands.BadArgument("This plugin is already off.")
            plugins[0].remove(self.name)
        await db.execute("UPDATE guild_settings SET plugins_off = $1 WHERE guild_id = $2", plugins[0], guild_id)

    async def turn_off(self, db, guild_id):
        await self.set_plugin(db, guild_id, False)

    async def turn_on(self, db, guild_id):
        await self.set_plugin(db, guild_id)