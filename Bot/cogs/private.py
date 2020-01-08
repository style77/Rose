import collections
from datetime import date, timedelta, datetime

from discord.ext import commands, tasks


class Private(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #     self.count_messages.start()
    #     self._send = False
    #
    # @tasks.loop(seconds=60.0)
    # async def count_messages(self):
    #     try:
    #         if not self._send:
    #             # now = datetime.utcnow()
    #             # if now >= now.replace(hour=0):
    #             channel = self.bot.get_channel(538481597205446687)
    #
    #             counter = collections.Counter()
    #
    #             yesterday = date.today() - timedelta(days=1)
    #
    #             async for message in channel.history(limit=None, after=yesterday):
    #                 counter[message.author.id] += 1
    #
    #             await channel.send(f"{counter}")
    #
    #             self._send = True
    #     except Exception as e:
    #         print(e)

    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild:
            return

        if message.guild.id == 538366293921759233:
            replies = {
                "despacito": "wszystko z toba dobrze?",
                "<@185712375628824577>": "https://cuck.host/SRLevrs.png",
                "kk": "Ile czasu zaoszczędziłeś tym skrótem?",
                "Xd": "ale beka Xddd",
                'kys': 'Sam sie zabij kurwo',
                ':)': "https://cuck.host/NNYkbyv.png",
                ':smiley:': "https://cuck.host/NNYkbyv.png",
                "jd": "Jebac disa kurwe zwisa syna szatana orka jebanego tibijskiego",
                "jebac disa": "tez tak mysle",
                "dobranoc": "smacznego",
                "ale beka": "no",
                "Ale beka": "No",
                "x": "kurwa\nd",
                "mam iphone": "ｓｏ  ｅｄｇｙ",
                "mam iphona": "ｓｏ  ｅｄｇｙ"
            }
            if message.content in replies:
                x = replies[message.content]
                await message.channel.send(x)

            if message.content.lower() == "ok":
                reacts = ["🇩", "🇮", "🇪"]
                for reaction in reacts:
                    await message.add_reaction(reaction)

            if message.content.lower() in ["twoj stary", "twój stary", "twuj stary"]:
                reacts = ["➕", "1\N{combining enclosing keycap}"]
                for reaction in reacts:
                    await message.add_reaction(reaction)

            if message.content.lower() in ["koham cie", "kocham cię", "kocham cie", "koham cię"]:
                reacts = ["🇯", "🅰", "🇨", "🅱", "🇹", "🇪", "🇿"]
                for reaction in reacts:
                    await message.add_reaction(reaction)


def setup(bot):
    bot.add_cog(Private(bot))