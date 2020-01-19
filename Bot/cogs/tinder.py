import asyncio
import json

import discord
from enum import Enum

from discord.ext import commands

from .classes.other import Plugin
from .classes.user import User


ORIENTATION_MAP = {
    0: "straight",
    1: "homo",
    2: "bi",
    3: "other"
}

SEX_MAP = {
    0: "male",
    1: "female",
    2: "other",
}


class Tinder(Plugin):
    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

        self._creating_account = list()

    async def find_similiar(self, user):
        # rating = 0
        # if fuzzy.similiar(user.tinder['hobbies'], user1.tinder['hobbies']):
        # rating += 1
        # if user1.tinder['age'] - 3 <= user.tinder['age'] <= user1.tinder['age'] + 5:
        # rating = 1
        users = await self.bot.db.fetch("SELECT * FROM users WHERE $1 - 4 <= (users.tinder->>'age')::int AND (users.tinder->>'age')::int <= $1 + 4", user.tinder['age'])
        if not users:
            return None
        else:
            return users

    @commands.group(invoke_without_command=True)
    async def tinder(self, ctx):
        z = []
        for cmd in ctx.command.commands:
            z.append(f"- {cmd.name}")

        return await ctx.send(ctx.lang['commands_group'].format('\n'.join(z)))

    @tinder.command()
    @commands.cooldown(1, 150, commands.BucketType.user)
    async def create(self, ctx):
        if ctx.author.id in self._creating_account:
            return await ctx.send(ctx.lang['already_creating_account'])

        self._creating_account.append(ctx.author.id)

        author = await self.bot.fetch_user_from_database(ctx.author.id)
        if author.tinder:
            c = await ctx.confirm(ctx.lang['wants_to_create_new_tinder'].format(ctx.prefix), ctx.author)
            if not c:
                return await ctx.send(ctx.lang['abort'])
        #     self._creating_account.remove(ctx.author.id)
        #     return await ctx.send(ctx.lang['already_has_tinder_account'])

        msg = await ctx.send(ctx.lang['trying_to_dm'])
        try:
            ch = await ctx.author.create_dm()
            await ch.send(ctx.lang['first_tinder_action'])
        except discord.HTTPException:
            self._creating_account.remove(ctx.author.id)
            return await msg.edit(content=ctx.lang['failed_to_dm'].format(ctx.author.mention))
        await msg.edit(content=ctx.lang['send_dm'].format(ctx.author.mention))

        data = {}

        def default_check(m):
            return m.author == ctx.author and m.channel == ch and m.guild is None

        try:
            name = await self.bot.wait_for('message', check=default_check, timeout=160)  # cuz its first question
        except asyncio.TimeoutError:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['TimeoutError2'])
        data['name'] = name.content

        await ch.send(ctx.lang['second_tinder_action'])
        try:
            age = await self.bot.wait_for('message', check=default_check, timeout=60)
        except asyncio.TimeoutError:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['TimeoutError2'])

        if not str(age.content).isdigit():
            self._creating_account.remove(ctx.author.id)
            return await ch.send(f"{ctx.lang['must_be_number']}\n{ctx.lang['abort']}")

        data['age'] = int(age.content)

        await ch.send(ctx.lang['third_tinder_action'].format(', '.join(SEX_MAP.values())))
        try:
            sex = await self.bot.wait_for('message', check=default_check, timeout=60)
        except asyncio.TimeoutError:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['TimeoutError2'])

        for key, value in SEX_MAP.items():
            if value == sex.content.lower():
                data['sex'] = key

        if 'sex' not in data:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['not_correct_choose'].format(', '.join(SEX_MAP.values())))

        await ch.send(ctx.lang['fourth_tinder_action'].format(', '.join(ORIENTATION_MAP.values())))
        try:
            orientation = await self.bot.wait_for('message', check=default_check, timeout=60)
        except asyncio.TimeoutError:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['TimeoutError2'])

        for key, value in ORIENTATION_MAP.items():
            if value == orientation.content.lower():
                data['orientation'] = key

        if 'orientation' not in data:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['not_correct_choose'].format(', '.join(ORIENTATION_MAP.values())))

        await ch.send(ctx.lang['fifth_tinder_action'])
        try:
            desc = await self.bot.wait_for('message', check=default_check, timeout=200)
        except asyncio.TimeoutError:
            self._creating_account.remove(ctx.author.id)
            return await ch.send(ctx.lang['TimeoutError2'])

        if desc.content.lower() in ['cancel', 'skip']:
            desc = ''
        else:
            desc = desc.content

        data['desc'] = desc

        data['data'] = {"skipped": [],
                        "hearted": []}

        self._creating_account.remove(ctx.author.id)
        await self.bot.db.execute("UPDATE users SET tinder = $1 WHERE id = $2", json.dumps(data), ctx.author.id)
        await ctx.send(ctx.lang['created_tinder_acc_for'].format(ctx.author.mention))
        await ch.send(ctx.lang['created_tinder_acc'])

    @tinder.command()
    @commands.cooldown(1, 7, commands.BucketType.user)
    async def edit(self, ctx, key, *, value):
        author = await self.bot.fetch_user_from_database(ctx.author.id)
        if not author.tinder:
            return await ctx.send(ctx.lang['no_tinder_account'].format(ctx.prefix))

        key = key.lower()

        proper_keys = ['age', 'desc', 'name', 'orientation', 'sex']
        if key not in proper_keys:
            return await ctx.send(ctx.lang['not_correct_choose'].format(', '.join(proper_keys)))

        req = author.tinder

        if key == "orientation":
            orient = None
            for key_, value_ in ORIENTATION_MAP.items():
                if value_ == value.lower():
                    value = orient = key

            if not orient:
                return await ctx.send(ctx.lang['not_correct_choose'].format(', '.join(ORIENTATION_MAP.values())))

            req[key] = orient

        elif key == "sex":
            sex = None
            for key_, value_ in SEX_MAP.items():
                if value_ == value.lower():
                    value = sex = key

            if not sex:
                return await ctx.send(ctx.lang['not_correct_choose'].format(', '.join(SEX_MAP.values())))

        elif key == "age":
            if not str(value).isdigit():
                return await ctx.send(ctx.lang['must_be_number'])
            value = int(value)

        req[key] = value
        await self.bot.db.execute("UPDATE users SET tinder = $1 WHERE id = $2", json.dumps(req), ctx.author.id)
        await ctx.send(ctx.lang['updated_setting'].format(key, value))

    @tinder.command()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def matchme(self, ctx):
        author = await self.bot.fetch_user_from_database(ctx.author.id)
        if not author.tinder:
            return await ctx.send(ctx.lang['no_tinder_account'].format(ctx.prefix))

        users = await self.find_similiar(author)

        # if author._raw in users:
        #     users.remove(author._raw)

        e = discord.Embed()

        msg = None

        reactions = ['\U0001f494', '\U00002764', '\U000023f9']

        def ch(r, u):
            return r.message.id == msg.id and u.id == ctx.author.id

        reacted = list()
        hearted = list()
        skipped = list()

        z = list()
        z.extend(author.tinder['data']['hearted'])
        z.extend(author.tinder['data']['skipped'])

        last = None

        empty_embed = discord.Embed(title=ctx.lang['no_more_people'], color=self.bot.color)

        # e.set_author(name=ctx.author.name, icon_url=ctx.author.avatar_url)

        for user in users:
            print(user)
            print(users)
            print(len(users))
            print(reacted)

            if user['id'] in z:
                reacted.append(user['id'])
                continue

            if user == last:
                print('empty')
                await msg.clear_reactions()
                await msg.edit(embed=empty_embed)
                break

            last = user

            if user['id'] in reacted:
                continue

            if [user['id'] for user in users] == reacted:
                print('all')
                await msg.clear_reactions()
                await msg.edit(embed=empty_embed)
                break

            if user['id'] == author.id:
                reacted.append(user['id'])
                continue

            user = User(self.bot, user)
            e.title = user.tinder['name']
            fmt = "Age: **{}**\nSex: **{}**\nOrientation: **{}**\n\n{}"
            e.description = fmt.format(user.tinder['age'], SEX_MAP[user.tinder['sex']],
                                       ORIENTATION_MAP[user.tinder['orientation']], user.tinder['desc'])

            if not msg:
                msg = await ctx.send(embed=e)

                for react in reactions:
                    await msg.add_reaction(react)
            else:
                await msg.edit(embed=e)

            if len(users) <= 1:
                print('empty')
                await msg.clear_reactions()
                await msg.edit(embed=empty_embed)
                break

            try:
                r, u = await self.bot.wait_for('reaction_add', check=ch, timeout=60)
            except asyncio.TimeoutError:
                return await msg.delete()

            if str(r.emoji) == reactions[0]:
                skipped.append(user.id)
                reacted.append(user.id)
                e.set_author(name=f"{user.tinder['name']} \U0001f494")
                users.remove(user._raw)
            elif str(r.emoji) == reactions[1]:
                if ctx.author.id in user.tinder['data']['hearted']:
                    try:
                        member = self.bot.get_user(user.id) or self.bot.fetch_user(user.id)
                        await ctx.author.send(ctx.lang['we_ve_got_a_match'].format(member, member.mention))

                        await member.send(ctx.lang['we_ve_got_a_match'].format(ctx.author, ctx.author.mention))
                    except discord.HTTPException:
                        pass

                hearted.append(user.id)
                reacted.append(user.id)
                e.set_author(name=f"{user.tinder['name']} \U00002764")
                users.remove(user._raw)
            elif str(r.emoji) == reactions[2]:
                await ctx.send(ctx.lang['abort'])
                await msg.delete()
                break
            else:
                await ctx.send(ctx.lang['abort'])
                await msg.delete()
                break

            await msg.edit(embed=e)
            await msg.remove_reaction(str(r.emoji), ctx.author)

        if not msg:
            await ctx.send(ctx.lang['no_one_found'].format(ctx.prefix))
        else:
            await msg.clear_reactions()
            await msg.edit(embed=empty_embed)

        print(hearted, skipped)

        req = author.tinder

        req['data']['hearted'].extend(hearted)
        req['data']['skipped'].extend(skipped)
        print(author.tinder)
        print(req)
        await self.bot.db.execute("UPDATE users SET tinder = $1 WHERE id = $2", json.dumps(req), ctx.author.id)

        if msg:
            await asyncio.sleep(5)
            await msg.delete()


def setup(bot):
    bot.add_cog(Tinder(bot))
