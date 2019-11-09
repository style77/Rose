import dateparser
from discord.ext.commands import Converter, BadArgument, UserInputError, MemberConverter
from discord.ext import commands
import re
from datetime import datetime, timezone, timedelta
from dateutil.relativedelta import relativedelta
import parsedatetime as pdt
import arrow
import pytz
import json
import discord

time_regex = re.compile(r"(?:(\d{1,5})(h|hr|hrs|s|sec|m|min|d|w|mo|y))+?")
link_regex = re.compile(
    r"((http(s)?(\:\/\/))+(www\.)?([\w\-\.\/])*(\.[a-zA-Z]{2,3}\/?))[^\s\b\n|]*[^.,;:\?\!\@\^\$ -]")
time_dict = {"h": 3600, "hr": 3600, "hrs": 3600, "s": 1, "sec": 1, "min": 60, "m": 60,
             "d": 86400, "y": 31536000, "mo": 2592000, "w": 604800}
hrs_re_en = re.compile("(?<=in )[^.]*")
hrs_re_pl = re.compile("(?<=w )[^.]*")
hrs_re_pl2 = re.compile("(?<=za )[^.]*")

compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                            (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                            (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                            (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                            (?:(?P<hours>[0-9]{1,5})(?:hours?|h|hr|hrs))?        # e.g. 12h
                            (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m|min))?    # e.g. 10m
                            (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s|sec))?    # e.g. 15s
                        """, re.VERBOSE)

class ShortTime:
    def __init__(self, argument, *, now=None):
        match = compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise BadArgument('Zły czas')
        now = now or datetime.now()

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        self.dt = now + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        lang = await get_language(ctx.bot, ctx.guild.id)
        if lang == "PL":
            now = ctx.message.created_at + timedelta(hours=2)
        else:
            now = ctx.message.created_at
        return cls(argument, now=now)


class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = now or datetime.now()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise BadArgument()

        if not status.hasTime:
            dt = dt.replace(hour=now.hour, minute=now.minute,
                            second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        lang = await get_language(ctx.bot, ctx.guild.id)
        if lang == "PL":
            now = ctx.message.created_at + timedelta(hours=2)
        else:
            now = ctx.message.created_at
        return cls(argument, now=now)


class Time(HumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)

        if self._past:
            raise BadArgument()


class UserFriendlyTime(commands.Converter):

    def __init__(self, converter=None, *, default=None):
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            raise TypeError('commands.Converter subclass necessary.')

        self.converter = converter
        self.default = default

    async def check_constraints(self, ctx, now, remaining):
        if self.dt < now:
            raise commands.BadArgument('This time is in the past.')

        if not remaining:
            if self.default is None:
                raise commands.BadArgument('Missing argument after the time.')
            remaining = self.default

        if self.converter is not None:
            self.arg = await self.converter.convert(ctx, remaining)
        else:
            self.arg = remaining
        return self

    async def convert(self, ctx, argument):
        try:
            calendar = HumanTime.calendar
            regex = compiled
            lang = await get_language(ctx.bot, ctx.guild.id)
            if lang == "PL":
                now = ctx.message.created_at + timedelta(hours=2)
            else:
                now = ctx.message.created_at

            match = regex.match(argument)
            if match is not None and match.group(0):
                data = {k: int(v)
                        for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end():].strip()
                self.dt = now + relativedelta(**data)
                return await self.check_constraints(ctx, now, remaining)

            # apparently nlp does not like "from now"
            # it likes "from x" in other cases though so let me handle the 'now' case
            if argument.endswith('from now'):
                argument = argument[:-8].strip()

            if argument[0:2] == 'me':
                # starts with "me to", "me in", or "me at "
                if argument[0:6] in ('me to ', 'me in ', 'me at '):
                    argument = argument[6:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                raise commands.BadArgument(
                    'Invalid time provided, try e.g. "tomorrow" or "3 days".')

            # handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time

            # first the first two cases:
            dt, status, begin, end, dt_string = elements[0]

            if not status.hasDateOrTime:
                raise commands.BadArgument(
                    'Invalid time provided, try e.g. "tomorrow" or "3 days".')

            if begin not in (0, 1) and end != len(argument):
                raise commands.BadArgument('Time is either in an inappropriate location, which '
                                           'must be either at the end or beginning of your input, '
                                           'or I just flat out did not understand what you meant. Sorry.')

            if not status.hasTime:
                # replace it with the current time
                dt = dt.replace(hour=now.hour, minute=now.minute,
                                second=now.second, microsecond=now.microsecond)

            # if midnight is provided, just default to next day
            if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
                dt = dt.replace(day=now.day + 1)

            self.dt = dt

            if begin in (0, 1):
                if begin == 1:
                    # check if it's quoted:
                    if argument[0] != '"':
                        raise commands.BadArgument(
                            'Expected quote before time input...')

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument(
                            'If the time is quoted, you must unquote it.')

                    remaining = argument[end + 1:].lstrip(' ,.!')
                else:
                    remaining = argument[end:].lstrip(' ,.!')
            elif len(argument) == end:
                remaining = argument[:begin].strip()

            return await self.check_constraints(ctx, now, remaining)
        except:
            import traceback
            traceback.print_exc()
            raise

class EasyTime(Converter):
    async def convert(self, ctx, argument):
        x = re.search(hrs_re_en, argument)
        z = re.search(hrs_re_pl, argument)
        z2 = re.search(hrs_re_pl2, argument)
        if x:
            date = dateparser.parse(x.group(1), languages=['pl', 'en'])
            if date is not None:
                return date
        if z:
            date = dateparser.parse(z.group(1), languages=['pl', 'en'])
            if date is not None:
                return date
        if z2:
            date = dateparser.parse(z2.group(1), languages=['pl', 'en'])
            if date is not None:
                return date
        return None

class EasyOneDayTime(Converter):
    async def convert(self, ctx, argument):
        args = argument.lower()
        matches = re.findall(time_regex, args)
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise BadArgument()
            except ValueError:
                raise BadArgument()
            return time

class VexsTimeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        args = argument.lower()
        matches = re.findall(time_regex, args)
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise commands.BadArgument("{} is an invalid time-key! h/m/s/d are valid!".format(k))
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time


class EasyOneDayTime2(Converter):
    async def convert(self, ctx, argument):
        args = argument.lower()
        matches = time_regex.match(args)
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise BadArgument()
            except ValueError:
                raise BadArgument()
        if matches.group(1) in ["y"]:
            return datetime(year=int(time))
        if matches.group(1) in ["mo"]:
            return datetime(month=int(time))
        if matches.group(1) in ["d"]:
            return datetime(day=int(time))
        if matches.group(1) in ["h", "hr", "hrs"]:
            return datetime(hour=int(time))
        if matches.group(1) in ["m", "min"]:
            return datetime(minute=int(time))
        if matches.group(1) in ["s", "sec"]:
            return datetime(second=int(time))

# PrettyTime jest psudo converterem, to tylko funkcja ktora zwraca dane.
class PrettyTime:
    def __init__(self, lang):
        self.lang = lang

    def convert(self, argument=None, reverse=False):
        if self.lang == "PL":
            return self._convert_pl(argument=argument, reverse=reverse)
        else:
            return self._convert_eng(argument=argument, reverse=reverse)


    def _convert_pl(self, argument=None, reverse=False):
        l = arrow.get(argument)
        return l.humanize(locale='pl')

    def _convert_eng(self, argument=None, reverse=False):
        l = arrow.get(argument)
        return l.humanize()

class urlConverter(Converter):
    async def convert(self, ctx, argument):
        if argument is None:
            raise UserInputError()
        member = None
        try:
            member = await MemberConverter().convert(ctx, argument)
        except Exception:
            pass
        if isinstance(member, discord.Member):
            return str(member.avatar_url)
        else:
            match = re.findall(link_regex, argument)
            if match:
                return argument
            else:
                raise BadArgument()

class EmojiConverter(Converter):
    async def convert(self, ctx, argument):
        try:
            em = await commands.EmojiConverter().convert(ctx, argument)
            return f"<:{em.name}:{em.id}>"
        except Exception:
            try:
                em = await commands.PartialEmojiConverter().convert(ctx, argument)
                return f"<:{em.name}:{em.id}>"
            except Exception as e:
                with open(r'cogs/utils/emoji_map.json','r') as f:
                    line = json.load(f)
                if argument in line.values():
                    return argument
                else:
                    raise BadArgument()


class TrueFalseError(commands.CommandError):
    pass


class TrueFalseConverter(Converter):
    async def convert(self, ctx, argument):
        if not argument:
            raise TrueFalseError()
        elif str(argument).lower() in ['true', '1', 'enable']:
            return True
        elif str(argument).lower() in ['false', '0', 'disable']:
            return False
    

class ModerationReason(commands.Converter):
    async def convert(self, ctx, argument):
        return f"[{ctx.author}]: {argument}"[:512]


class BannedMember(commands.Converter):
    async def convert(self, ctx, argument):
        ban_list = await ctx.guild.bans()
        try:
            member_id = int(argument, base=10)
            entity = discord.utils.find(lambda u: u.user.id == member_id, ban_list)
        except ValueError:
            entity = discord.utils.find(lambda u: str(u.user) == argument, ban_list)
        if entity is None:
            raise commands.UserInputError()
        return entity


class SafeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = discord.utils.escape_markdown(argument)
        argument = discord.utils.escape_mentions(argument)
        return argument


def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.datetime.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                #if not brief:
                    #output.append(format(plural(weeks), 'week'))
                #else:
                output.append(f'{weeks}w')

        if elem <= 0:
            continue

        #if brief:
        output.append(f'{elem}{brief_attr}')
        #else:
            #output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        #if not brief:
            #return human_join(output, final='and') + suffix
        #else:
        return ' '.join(output) + suffix
