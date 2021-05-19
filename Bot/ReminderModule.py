import asyncio
import re

from enum import Enum
from datetime import datetime, timedelta
from dateutil import tz

import copy

import discord
from discord.ext import commands, tasks
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.model import SlashCommandOptionType

from datetime import datetime, timedelta

from lib.Connector import Connector
from lib.Reminder import Reminder
import lib.input_parser

from lib.Analytics import Analytics
from ReminderListing import ReminderListing

class ReminderModule(commands.Cog):

    REMIND_FORMAT_HELP = '```'\
                'allowed absolutes are\n'\
                '\t• eoy - remind at end of year\n'\
                '\t• eom - remind at end of month\n'\
                '\t• eow - remind at end of working week (Friday night)\n'\
                '\t• eod - remind at end of day\n'\
                '\n'\
                'allowed intervals are\n'\
                '\t• y(ears)\n'\
                '\t• mo(nths)\n'\
                '\t• w(eeks)\n'\
                '\t• d(ays)\n'\
                '\t• h(ours)\n'\
                '\t• mi(ns)\n'\
                '\n'\
                'you can combine relative intervals like this\n'\
                '\t1y 1mo 2 days -5h\n'\
                '\n'\
                'dates are supported aswell, you can try different formats\n'\
                '\t• 5 jul, 5th july, july 5\n'\
                '\t• 23 sept at 3pm or 23 sept at 15:00\n'\
                '\t• 2050\n'\
                'Note: the parser uses day first (1.2.2021 -> 1st January)\n'\
                '      absolute days do respect the /timezone of the server\n'\
                '\n'\
                'examples:\n'\
                '\t/remindme 1y Hello future me\n'\
                '\t/remindme 2 h drink some water\n'\
                '\t/remindme 1w 2d hello there\n'\
                '\t/remind @User 24 dec Merry Christmas\n'\
                '\t/remind @User eoy Happy new year\n'\
                '\n'\
                'the reminder can occur as much as 1 minute delayed```\n'\
                'If you find a bug in the parser, please reach out to us.\n'\
                'Contact details are at `Get Support` on [top.gg](https://top.gg/bot/831142367397412874)'\
                ' or on [Github](https://github.com/Mayerch1/RemindmeBot)'


    @staticmethod
    def to_int(num_str: str, base: int=10):
        
        try:
            conv_int = int(num_str, base)
        except ValueError:
            conv_int = None
        finally:
            return conv_int
    

    # =====================
    # internal functions
    # =====================

    def __init__(self, client):
        self.client = client

        print('starting reminder event loops')
        self.check_pending_reminders.start()
        self.check_reminder_cnt.start()



        


    async def print_reminder_dm(self, rem: Reminder, err_msg=None):
        # fallback to dm
        # target must be resolved, otherwise dm cannot be created

        try:
            target = await self.client.fetch_user(rem.target)
        except discord.errors.NotFound:
            print(f'cannot find user {rem.target} for reminder DM fallback')
            return

        # dm if channel not existing anymor
        dm =  await target.create_dm()

        eb = await rem.get_embed(self.client, is_dm=True)
        
        # first fallback is string-only message
        # second fallback is dm to user
        # DM never requires user mention (DM itself is a ping)
        try:
            await dm.send(embed=eb)
            if err_msg:
                await dm.send(f'||{err_msg}||')
        except discord.errors.Forbidden:

            try:
                await dm.send(rem.get_string())
            except discord.errors.Forbidden:
                print(f'failed to send reminder as DM fallback')


    async def print_reminder(self, rem: Reminder):

        # reminder is a DM reminder
        if not rem.g_id:
            await self.print_reminder_dm(rem)
            return

        guild = self.client.get_guild(rem.g_id)
        channel = guild.get_channel(rem.ch_id)

        # no need to resolve author, target is sufficient

        if not channel:
            err = f'`You are receiving this dm, as the reminder channel on \'{guild.name}\' is not existing anymore.`'
            await self.print_reminder_dm(rem, err)
            return

        eb = await rem.get_embed(self.client)
        

        # first fallback is string-only message
        # second fallback is dm to user

        perms = channel.permissions_for(guild.me)
        

        if perms.send_messages and perms.embed_links:
            try:
                # embed does not hold user mention
                await channel.send(f'<@!{rem.target}>', embed=eb)
                return
            except discord.errors.Forbidden:
                pass


        if perms.send_messages:
            try:
                # string already holds user mention
                await channel.send(rem.get_string())
                return
            except discord.errors.Forbidden:
                pass


        err = f'`You are receiving this dm, as I do not have permission to send messages into the channel \'{channel.name}\' on \'{guild.name}\'.`'

        await self.print_reminder_dm(rem, err)



    @staticmethod
    def delta_to_str(delta):
            ret_str = ''
            secs = delta.total_seconds()

            hours, rem = divmod(secs, 3600)
            mins, secs = divmod(rem, 60)
            
            if hours > 48:
                return '{:d} days ({:02d} hours)'.format(int(hours/24), int(hours))
            elif hours > 0:
                return '{:02d} h {:02d} m'.format(int(hours), int(mins))
            else:
                return '{:d} minutes'.format(int(mins))


    async def process_reminder(self, ctx, author, target, period, message):

        if ctx.guild:
            tz_str = Connector.get_timezone(author.guild.id)

            # try and get the last message, for providing a jump link
            try:
                last_msg = await ctx.channel.history(limit=1).flatten()
            except:
                last_msg = None

            last_msg = last_msg[0] if last_msg else None
        else:
            tz_str = 'UTC'
            last_msg = None

        
        err = False

        utcnow = datetime.utcnow()
        remind_at, info = lib.input_parser.parse(period, utcnow, tz_str)


        if (remind_at - utcnow) <= timedelta(hours=0):
            out_str = ''
            if info:
                print('received invalid format string')
                out_str += f'```Parsing hints:\n{info}```\n'
                out_str += ReminderModule.REMIND_FORMAT_HELP
                Analytics.invalid_f_string()
            else:
                print('received negative reminder interval')
                out_str += f'```the interval must be greater than 0```'
                Analytics.invalid_f_string()

            embed = discord.Embed(title='Failed to create the reminder', description=out_str)
            await ctx.send(embed=embed, hidden=True)
            return


        rem = Reminder()

        if ctx.guild:
            rem.g_id = ctx.guild.id
            rem.ch_id = ctx.channel_id
        else:
            # command was called in DM
            rem.g_id = None
            rem.ch_id = None

        rem.msg = message
        rem.at = remind_at
        rem.author = author.id
        rem.target = target.id
        rem.created_at = utcnow
        rem.last_msg_id = last_msg.id if last_msg else None

        # the id is required in case the users wishes to abort
        rem_id = Connector.add_reminder(rem)

        if rem.author == rem.target:
            Analytics.add_self_reminder(rem)
            print('added reminder for self')
        else:
            Analytics.add_foreign_reminder(rem)
            print('added reminder')
        
        # convert reminder period to readable delta
        # convert utc date into readable local time (locality based on server settings)
        delta_str = ReminderModule.delta_to_str(remind_at-utcnow)
        if tz_str == 'UTC':
            # this workaround is required, as system uses german term for UTC
            at_str = remind_at.strftime('%Y/%m/%d %H:%M UTC')
        else:
            at_str = remind_at.replace(tzinfo=tz.UTC).astimezone(tz.gettz(tz_str)).strftime('%Y/%m/%d %H:%M %Z')

        if target == author:
            out_str = f'Reminding you in `{delta_str}` at `{at_str}`.'
        else:
             out_str = f'Reminding {target.name} in `{delta_str}` at `{at_str}`.'
      
        if (remind_at-utcnow) < timedelta(minutes=5):
            out_str += '\nBe aware that the reminder can be as much as 1 minute delayed'

        if info:
            out_str += f'\n```Parsing hints:\n{info}```'
        
        out_str += '\n\nYou can cancel this reminder within the next 3 minutes by reacting to this message with ❌'

        # delta_to_str cannot take relative delta
        msg = await ctx.send(out_str, delete_after=300)

        try:
            await msg.add_reaction('❌')
        except:
            pass

        def check(reaction, user):
            return user.id == author.id and reaction.emoji == '❌' and reaction.message.id == msg.id

        try:
            react, _ = await self.client.wait_for('reaction_add', timeout=180, check=check)
        except asyncio.exceptions.TimeoutError:
            try:
                await msg.add_reaction('⏲')
                await msg.remove_reaction('❌', self.client.user)
            except:
                # fails if reaction couldn't be added in last step
                pass
        else:
            # delete the reminder again
            if Connector.delete_reminder(rem_id):
                await ctx.send('Deleted reminder')
                Analytics.delete_reminder()
                print('deleted reminder')


    # =====================
    # events functions
    # =====================

    @commands.Cog.listener()
    async def on_ready(self):
        print('ReminderModule loaded')


    @tasks.loop(minutes=1)
    async def check_pending_reminders(self):
        now = datetime.utcnow()

        pending_rems = Connector.pop_elapsed_reminders(now.timestamp())
        
        for reminder in pending_rems:
            await self.print_reminder(reminder)
    

    @check_pending_reminders.before_loop
    async def check_pending_reminders_before(self):
        await self.client.wait_until_ready()

   

    @tasks.loop(minutes=15)
    async def check_reminder_cnt(self):
        now = datetime.utcnow()

        rems = Connector.get_reminder_cnt()
        Analytics.active_reminders(rems)
        

    @check_reminder_cnt.before_loop
    async def check_reminder_cnt_before(self):
        await self.client.wait_until_ready()

    # =====================
    # commands functions
    # =====================

    @cog_ext.cog_slash(name='remind', description='set a reminder for another user',
                        options=[
                            create_option(
                                name='user',
                                description='the user you want to remind',
                                required=True,
                                option_type=SlashCommandOptionType.USER
                            ),
                            create_option(
                                name='period',
                                description='the time after you\'re reminded',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            ),
                            create_option(
                                name='message',
                                description='the bot will remind you with this message',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            )
                        ])
    @commands.guild_only()
    async def add_remind_user(self, ctx, user, period, message):
        
        await self.process_reminder(ctx, ctx.author, user, period, message)
    
   
    @cog_ext.cog_slash(name='remindme', description='set a reminder after a certain time period',
                        options=[
                            create_option(
                                name='period',
                                description='the time after you\'re reminded',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            ),
                            create_option(
                                name='message',
                                description='the bot will remind you with this message',
                                required=True,
                                option_type=SlashCommandOptionType.STRING
                            )
                        ])
    async def add_remind_author(self, ctx, period, message):
        
        await self.process_reminder(ctx, ctx.author, ctx.author, period, message)
        
       
    @cog_ext.cog_slash(name='reminder_list', description='List all reminders created by you')
    async def list_reminders(self, ctx):

        if ctx.guild:
            await ReminderListing.show_reminders_dm(self.client, ctx)
        else:
            await ReminderListing.show_private_reminders(self.client, ctx)


def setup(client):
    client.add_cog(ReminderModule(client))
